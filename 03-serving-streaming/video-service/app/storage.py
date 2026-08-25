"""
Cliente S3/MinIO e operações de multipart upload / notificações / bucket setup.

Duas coisas importantes de arquitetura aqui:

1. DOIS clientes boto3, não um só. `s3` fala com o MinIO pela rede interna do
   Docker (`http://minio:9000`) — usado pra tudo que roda dentro do
   container (criar bucket, completar upload, baixar/subir arquivo). `s3_public`
   fala com o MinIO pelo endereço que o NAVEGADOR do usuário consegue
   alcançar (`http://localhost:9000` em dev, ou o domínio público em
   produção) — usado só pra gerar URLs que vão ser entregues pro cliente
   (as URLs de cada parte do multipart, e a URL do manifesto HLS).
   Se você usar o cliente errado em cada caso, ou a URL não assina certo
   (endpoint interno não resolve fora do Docker) ou o navegador não
   consegue nem alcançar o host.

2. `PART_SIZE` fixo em 16 MiB: acima do mínimo de 5 MiB exigido pelo S3/MinIO,
   e mantém o número de partes (e de requisições HTTP do navegador) razoável
   pra vídeos de alguns GB. É um número ajustável, não uma regra rígida.
"""

from __future__ import annotations

import json
import os

import boto3
from botocore.client import Config

S3_ENDPOINT_URL = os.environ["S3_ENDPOINT_URL"]
S3_PUBLIC_ENDPOINT_URL = os.environ.get("S3_PUBLIC_ENDPOINT_URL", S3_ENDPOINT_URL)
S3_BUCKET = os.environ["S3_BUCKET"]
AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# O alvo "PRIMARY" é registrado no lado do MinIO via variáveis de ambiente
# (ver o serviço `minio` no docker-compose.yml):
#   MINIO_NOTIFY_WEBHOOK_ENDPOINT_PRIMARY, _AUTH_TOKEN_PRIMARY, _ENABLE_PRIMARY.
# O `_ENABLE_PRIMARY=on` é fácil de esquecer — sem ele o alvo fica
# registrado mas desabilitado, e put_bucket_notification_configuration falha
# com "A specified destination ARN does not exist" (testado e confirmado).
NOTIFICATION_ARN = "arn:minio:sqs::PRIMARY:webhook"

PART_SIZE = 16 * 1024 * 1024  # 16 MiB — ver nota acima


def _client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
        # addressing_style "path" é obrigatório pro MinIO: sem isso o boto3
        # tenta montar a URL no formato "bucket.endpoint.com", que só existe
        # de verdade na AWS (virtual-hosted style), não no MinIO.
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


s3 = _client(S3_ENDPOINT_URL)
s3_public = _client(S3_PUBLIC_ENDPOINT_URL)


def raw_object_key(video_id: str, filename: str) -> str:
    return f"raw/{video_id}/{filename}"


def hls_prefix(video_id: str) -> str:
    return f"hls/{video_id}"


def ensure_bucket_ready() -> None:
    """Roda uma vez, no startup do video-service: cria o bucket (se não
    existir), libera leitura pública só do prefixo hls/ (os manifestos e
    segmentos — o vídeo bruto em raw/ continua privado), configura CORS
    (essencial: sem `ExposeHeaders: ["ETag"]` o navegador recebe o upload
    de cada parte com sucesso mas NUNCA consegue ler o header ETag da
    resposta — e sem o ETag não dá pra fechar o multipart upload depois),
    e registra a notificação de evento que dispara o webhook do FFmpeg.
    """
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if S3_BUCKET not in existing:
        s3.create_bucket(Bucket=S3_BUCKET)

    # Nada de put_bucket_cors aqui: essa versão do MinIO não implementa a API
    # de CORS por bucket (dá NotImplemented tanto via boto3 quanto via
    # `mc cors set` nativo — testado e confirmado). Isso não é um problema
    # de verdade: o CORS já é resolvido globalmente pelo servidor MinIO
    # (config `api.cors_allow_origin`, default "*"), e o header ETag já vem
    # exposto por padrão nessa configuração global — confirmado com um PUT
    # de teste simulando um navegador (Origin + leitura do header ETag na
    # resposta). Se um dia precisar restringir origins, isso se ajusta via
    # `mc admin config set local api cors_allow_origin=https://seu-dominio`,
    # não pela API de bucket.

    s3.put_bucket_policy(
        Bucket=S3_BUCKET,
        Policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{S3_BUCKET}/hls/*"],
                    }
                ],
            }
        ),
    )

    s3.put_bucket_notification_configuration(
        Bucket=S3_BUCKET,
        NotificationConfiguration={
            "QueueConfigurations": [
                {
                    "Id": "video-upload-complete",
                    "QueueArn": NOTIFICATION_ARN,
                    "Events": ["s3:ObjectCreated:CompleteMultipartUpload"],
                    "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "raw/"}]}},
                }
            ]
        },
    )


def create_multipart_upload(key: str, content_type: str) -> str:
    resp = s3.create_multipart_upload(Bucket=S3_BUCKET, Key=key, ContentType=content_type)
    return resp["UploadId"]


def presign_part(key: str, upload_id: str, part_number: int, expires_in: int = 3600) -> str:
    # Client PÚBLICO aqui: essa URL vai direto pro navegador.
    return s3_public.generate_presigned_url(
        ClientMethod="upload_part",
        Params={"Bucket": S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
        ExpiresIn=expires_in,
    )


def complete_multipart_upload(key: str, upload_id: str, parts: list[dict]) -> None:
    ordered = sorted(parts, key=lambda p: p["partNumber"])
    s3.complete_multipart_upload(
        Bucket=S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": [{"PartNumber": p["partNumber"], "ETag": p["etag"]} for p in ordered]},
    )


def abort_multipart_upload(key: str, upload_id: str) -> None:
    s3.abort_multipart_upload(Bucket=S3_BUCKET, Key=key, UploadId=upload_id)


def public_url(key: str) -> str:
    # Objeto público (prefixo hls/, liberado pela bucket policy acima) —
    # não precisa de presigned URL, e não expira.
    return f"{S3_PUBLIC_ENDPOINT_URL}/{S3_BUCKET}/{key}"


def download_file(key: str, local_path: str) -> None:
    s3.download_file(S3_BUCKET, key, local_path)


def upload_file(local_path: str, key: str, content_type: str | None = None) -> None:
    extra_args = {"ContentType": content_type} if content_type else {}
    s3.upload_file(local_path, S3_BUCKET, key, ExtraArgs=extra_args)
