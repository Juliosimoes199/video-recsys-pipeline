# video-service

Este serviço é **seu** — banco de dados, protocolo HLS, URLs pré-assinadas,
notificações e a transformação de vídeo. Implementa as rotas descritas em
[`../CONTRACT.md`](../CONTRACT.md).

## O que já é real

- **Upload multipart** direto pro MinIO (`app/storage.py`) — presigned URL
  por parte, `CompleteMultipartUpload` no fechamento.
- **MinIO → webhook → FFmpeg**: quando o multipart upload fecha, o MinIO
  dispara um evento (`s3:ObjectCreated:CompleteMultipartUpload`) pro webhook
  interno `POST /webhooks/minio`, que roda o FFmpeg em background
  (`app/transcode.py`) gerando HLS adaptativo (480p/720p/1080p) + thumbnail,
  e sobe tudo de volta pro MinIO.
- Bucket, política pública (só `hls/*` — o vídeo bruto em `raw/*` continua
  privado), e o registro da notificação são configurados sozinhos no
  startup (`storage.ensure_bucket_ready()`).
- **Sem upscale**: antes de transcodificar, roda `ffprobe` pra pegar a
  altura real do vídeo original e só gera renditions que não sejam maiores
  que ela (`app/transcode.py`, `_renditions_for`). Um vídeo de 360p não gera
  uma rendition falsa de "1080p" — gera só uma rendition na resolução real.
- **Persistência em Postgres** (`app/db.py`) — vídeos, comentários,
  notificações e canais sobrevivem a `docker compose stop/start`, restart
  de container e rebuild de imagem. Só `docker compose down -v` apaga de
  propósito (é isso que os volumes nomeados `pgdata`/`minio-data` no
  `docker-compose.yml` da raiz garantem).
- **Uma visualização por usuário, e o dono não conta**: `POST
  /videos/:id/view` usa uma tabela `video_views` com chave primária
  composta `(video_id, viewer_id)` — o mesmo usuário vendo o vídeo de novo
  não soma outra vez, e o endpoint nem tenta contar se `viewer_id ==
  ownerId` do vídeo.
- **Like/dislike e inscrição também com dedupe por usuário** —
  `video_reactions` (chave composta `(video_id, user_id)`, com CHECK
  garantindo que a reação só pode ser `like` OU `dislike`, nunca as duas)
  e `channel_subscriptions` (chave composta `(channel_id, subscriber_id)`).
  Clicar "like" repetidas vezes não soma de novo; trocar de like pra
  dislike decrementa um contador e incrementa o outro atomicamente; e não
  dá pra se inscrever no próprio canal (`CANNOT_SUBSCRIBE_SELF`).
- **Validação real do JWT do Clerk** (`app/auth.py`) — `current_user_id()`
  verifica a assinatura RS256 contra o JWKS do Clerk (`CLERK_JWKS_URL`,
  cacheado por processo — não busca de novo a cada requisição), valida
  `iss`/`exp`, e usa o `sub` como identidade real. Rotas de ação (upload,
  comentar, curtir, editar/apagar vídeo, etc.) devolvem `401` sem token
  válido; editar/apagar vídeo e apagar comentário também checam dono
  (`403` se não for seu — fechei os TODOs que já estavam marcados nessas
  rotas). `current_user_id_optional()` existe pra rotas que funcionam sem
  login (feed, detalhe do vídeo, `POST /videos/:id/view` — visitante
  anônimo assiste normalmente, só não soma na contagem de views).

## O que ainda é stub

- **Webhook do Clerk** — verificar a assinatura Svix em `/webhooks/clerk`
  antes de confiar no payload (`# TODO(python-service):` em
  [`app/main.py`](app/main.py)). O endpoint já funciona (faz upsert do
  canal), só não confirma a origem do payload ainda.

## Duas pegadinhas de MinIO que vale saber (se for mexer em `storage.py`)

- **`put_bucket_cors` não existe nessa versão do MinIO** (dá `NotImplemented`
  tanto via boto3 quanto via `mc cors set` nativo) — e não faz falta: o CORS
  já é global por padrão (`api.cors_allow_origin=*`), incluindo o header
  `ETag` exposto, que é o que o upload multipart precisa.
- **Alvo de notificação nomeado precisa de `_ENABLE_<nome>=on` explícito** —
  só `_ENDPOINT_<nome>` e `_AUTH_TOKEN_<nome>` não bastam; sem o `_ENABLE`,
  o alvo fica registrado mas inativo, e `put_bucket_notification_configuration`
  falha com "a specified destination ARN does not exist". E o header que o
  MinIO manda no webhook é `Authorization: Bearer <token>`, com prefixo.

## Rodando localmente sem Docker

```bash
cd video-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

A API sobe em `http://localhost:8000`, com docs automáticas em
`http://localhost:8000/docs`.
