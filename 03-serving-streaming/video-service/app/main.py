"""
video-service.

Implementa o contrato descrito em CONTRACT.md (na raiz do projeto). Upload
(multipart real via MinIO), a notificação de evento do MinIO, a
transcodificação com FFmpeg (ver storage.py e transcode.py), a
persistência (Postgres, ver db.py) e a validação do JWT do Clerk (ver
auth.py) já são de verdade. O que ainda é "de mentira": a verificação de
assinatura Svix do webhook do Clerk.

Cada ponto que ainda precisa virar "de verdade" está marcado com:
    # TODO(python-service): ...
"""

from __future__ import annotations

import math
import os
import uuid
from typing import Literal
from urllib.parse import unquote_plus

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db, storage, transcode
from .auth import current_user_id, current_user_id_optional

app = FastAPI(title="video-service")

MINIO_WEBHOOK_TOKEN = os.environ.get("MINIO_WEBHOOK_TOKEN")

# TODO(python-service): restringir para o(s) domínio(s) reais do frontend em produção.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_CHANNEL_ID = "user_demo"

# Stream HLS público, só para exercitar o player no frontend antes de
# qualquer upload de verdade.
DEMO_MANIFEST_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"


@app.on_event("startup")
def _startup() -> None:
    storage.ensure_bucket_ready()
    db.init_schema()
    _seed_if_empty()


def _seed_if_empty() -> None:
    # Idempotente: só semeia na primeira vez que o banco está vazio de
    # verdade. Sem isso, cada restart do container duplicaria os 3 vídeos
    # de demonstração (o Postgres agora persiste entre restarts).
    if db.list_videos(limit=1):
        return

    db.upsert_channel(
        {
            "id": DEMO_CHANNEL_ID,
            "displayName": "Canal Demo",
            "avatarUrl": "https://api.dicebear.com/9.x/thumbs/svg?seed=demo",
            "bio": "",
            "subscriberCount": 0,
        }
    )

    for i, title in enumerate(["Big Buck Bunny (demo)", "Sintel (demo)", "Tears of Steel (demo)"]):
        video_id = _new_id("vid")
        db.insert_video(
            {
                "id": video_id,
                "ownerId": DEMO_CHANNEL_ID,
                "title": title,
                "description": "Vídeo de demonstração gerado no startup do video-service.",
                "thumbnailUrl": f"https://picsum.photos/seed/{video_id}/640/360",
                "manifestUrl": DEMO_MANIFEST_URL,
                "status": "ready",
                "durationSeconds": 300 + i * 120,
                "viewCount": 100 * (i + 1),
                "likeCount": 10 * (i + 1),
                "dislikeCount": 1,
                "visibility": "public",
                "rawKey": None,
                "uploadId": None,
            }
        )


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def error(status_code: int, code: str, message: str):
    raise HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class PresignRequest(BaseModel):
    filename: str
    contentType: str
    sizeBytes: int


class PartInput(BaseModel):
    partNumber: int
    etag: str


class CompleteRequest(BaseModel):
    title: str
    description: str = ""
    visibility: Literal["public", "unlisted", "private"] = "public"
    parts: list[PartInput]


class PatchVideoRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    thumbnailUrl: str | None = None
    visibility: Literal["public", "unlisted", "private"] | None = None


class LikeRequest(BaseModel):
    action: Literal["like", "unlike", "dislike", "undislike"]


class CommentRequest(BaseModel):
    text: str
    parentId: str | None = None


class SubscribeRequest(BaseModel):
    action: Literal["subscribe", "unsubscribe"]


class ChannelPatchRequest(BaseModel):
    displayName: str | None = None
    bio: str | None = None
    avatarUrl: str | None = None


# ---------------------------------------------------------------------------
# Feed / busca
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/videos")
def list_videos_route(query: str | None = None, mine: bool = False, request: Request = None, cursor: str | None = None, limit: int = 24):
    # TODO(python-service): paginação real por cursor, filtro por visibilidade
    # (só o dono deveria ver os próprios vídeos "private"/"processing"), e
    # busca de verdade (full-text) em vez de ILIKE.
    owner_id = current_user_id(request) if mine else None  # mine=true exige login
    items = db.list_videos(query=query, owner_id=owner_id, limit=limit)
    return {"items": items, "nextCursor": None}


@app.get("/videos/{video_id}")
def get_video_route(video_id: str):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    return video


@app.get("/videos/{video_id}/status")
def video_status(video_id: str):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    return {"status": video["status"], "progress": 100 if video["status"] == "ready" else 0}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@app.post("/videos/upload/presign")
def presign_upload(body: PresignRequest, request: Request):
    user_id = current_user_id(request)
    # Garante um canal pro usuário mesmo que o webhook do Clerk ainda não
    # tenha rodado (ou não esteja configurado) — sem isso, o primeiro
    # upload de um usuário novo mostraria "Usuário" genérico em vez do
    # nome/avatar real até ele comentar ou editar o perfil.
    db.ensure_channel(user_id)
    video_id = _new_id("vid")
    key = storage.raw_object_key(video_id, body.filename)

    upload_id = storage.create_multipart_upload(key, body.contentType)

    part_count = max(1, math.ceil(body.sizeBytes / storage.PART_SIZE))
    parts = [
        {"partNumber": n, "url": storage.presign_part(key, upload_id, n)}
        for n in range(1, part_count + 1)
    ]

    db.insert_video(
        {
            "id": video_id,
            "ownerId": user_id,
            "title": body.filename,
            "description": "",
            "thumbnailUrl": None,
            "manifestUrl": None,
            "status": "uploading",
            "durationSeconds": 0,
            "viewCount": 0,
            "likeCount": 0,
            "dislikeCount": 0,
            "visibility": "public",
            "rawKey": key,
            "uploadId": upload_id,
        }
    )

    return {
        "videoId": video_id,
        "uploadId": upload_id,
        "key": key,
        "partSize": storage.PART_SIZE,
        "parts": parts,
        "expiresAt": db.get_video(video_id)["createdAt"],
    }


@app.post("/videos/{video_id}/complete")
def complete_upload(video_id: str, body: CompleteRequest, request: Request):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    if current_user_id(request) != video["ownerId"]:
        error(403, "FORBIDDEN", "Esse upload não é seu")

    with db.pool.connection() as conn:
        row = conn.execute("SELECT raw_key, upload_id FROM videos WHERE id = %s", (video_id,)).fetchone()
    if not row or not row["raw_key"] or not row["upload_id"]:
        error(409, "UPLOAD_NOT_IN_PROGRESS", "Não há upload em andamento para este vídeo")

    storage.complete_multipart_upload(
        row["raw_key"], row["upload_id"], [p.model_dump() for p in body.parts]
    )

    # Não marca como "ready" aqui: o MinIO ainda vai processar o
    # CompleteMultipartUpload e disparar o evento que chega em
    # /webhooks/minio — é lá que a transcodificação real acontece e o vídeo
    # vira "ready" (ou "failed").
    db.update_video(
        video_id,
        {
            "title": body.title,
            "description": body.description,
            "visibility": body.visibility,
            "status": "processing",
        },
    )

    return db.get_video(video_id)


@app.post("/webhooks/minio")
async def minio_webhook(request: Request, background_tasks: BackgroundTasks):
    # O MinIO manda o token configurado em MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_PRIMARY
    # com prefixo "Bearer " no header Authorization (confirmado testando —
    # não está claramente documentado).
    token = request.headers.get("authorization")
    if MINIO_WEBHOOK_TOKEN and token != f"Bearer {MINIO_WEBHOOK_TOKEN}":
        error(401, "INVALID_WEBHOOK_TOKEN", "Token de webhook inválido")

    payload = await request.json()

    for record in payload.get("Records", []):
        event_name = record.get("eventName", "")
        if "CompleteMultipartUpload" not in event_name:
            continue

        raw_key = unquote_plus(record["s3"]["object"]["key"])
        video = db.get_video_by_raw_key(raw_key)
        if not video:
            continue

        background_tasks.add_task(_process_transcode_job, video["id"], raw_key)

    return {"received": True}


async def _process_transcode_job(video_id: str, raw_key: str) -> None:
    video = db.get_video(video_id)
    if not video:
        return

    try:
        result = await transcode.transcode_video(video_id, raw_key)
        db.update_video(
            video_id,
            {
                "status": "ready",
                "manifestUrl": result["manifestUrl"],
                "thumbnailUrl": result["thumbnailUrl"],
                "durationSeconds": result["durationSeconds"],
            },
        )
        db.insert_notification(
            {
                "id": _new_id("ntf"),
                "userId": video["ownerId"],
                "type": "video.ready",
                "title": "Seu vídeo está pronto!",
                "body": video["title"],
                "videoId": video_id,
                "read": False,
            }
        )
    except Exception as exc:  # noqa: BLE001 — precisa capturar qualquer falha do ffmpeg
        db.update_video(video_id, {"status": "failed"})
        db.insert_notification(
            {
                "id": _new_id("ntf"),
                "userId": video["ownerId"],
                "type": "video.failed",
                "title": "Falha ao processar seu vídeo",
                "body": str(exc)[:200],
                "videoId": video_id,
                "read": False,
            }
        )


# ---------------------------------------------------------------------------
# Editar / apagar
# ---------------------------------------------------------------------------


@app.patch("/videos/{video_id}")
def patch_video(video_id: str, body: PatchVideoRequest, request: Request):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    if current_user_id(request) != video["ownerId"]:
        error(403, "FORBIDDEN", "Esse vídeo não é seu")

    fields = body.model_dump(exclude_none=True)
    db.update_video(video_id, fields)
    return db.get_video(video_id)


@app.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: str, request: Request):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    if current_user_id(request) != video["ownerId"]:
        error(403, "FORBIDDEN", "Esse vídeo não é seu")

    # TODO(python-service): apagar os objetos correspondentes no MinIO (raw/ e hls/).
    db.delete_video(video_id)
    return None


# ---------------------------------------------------------------------------
# Visualizações e reações
# ---------------------------------------------------------------------------


@app.post("/videos/{video_id}/view")
def register_view(video_id: str, request: Request):
    video = db.get_video(video_id)
    if not video:
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")

    # Visualização é opcionalmente autenticada: quem não está logado ainda
    # consegue assistir (o vídeo é público), só não soma no contador — não
    # temos como deduplicar um visitante anônimo (sem cookie/fingerprint,
    # que não implementamos), e prefiro não contar a contar errado.
    viewer_id = current_user_id_optional(request)
    if not viewer_id:
        return {"viewCount": video["viewCount"]}

    # O dono assistindo o próprio vídeo não conta como visualização — e
    # `db.register_view` já garante (via PRIMARY KEY (video_id, viewer_id))
    # que o MESMO usuário nunca soma uma segunda vez, não importa quantas
    # vezes ele reveja o vídeo depois.
    if viewer_id == video["ownerId"]:
        return {"viewCount": video["viewCount"]}

    view_count = db.register_view(video_id, viewer_id)
    return {"viewCount": view_count}


@app.post("/videos/{video_id}/like")
def like_video(video_id: str, body: LikeRequest, request: Request):
    if not db.get_video(video_id):
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")

    user_id = current_user_id(request)
    return db.set_reaction(video_id, user_id, body.action)


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------


@app.get("/videos/{video_id}/comments")
def list_comments_route(video_id: str, cursor: str | None = None, limit: int = 20):
    if not db.get_video(video_id):
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")
    return {"items": db.list_comments(video_id, limit=limit), "nextCursor": None}


@app.post("/videos/{video_id}/comments")
def add_comment(video_id: str, body: CommentRequest, request: Request):
    if not db.get_video(video_id):
        error(404, "VIDEO_NOT_FOUND", "Vídeo não encontrado")

    user_id = current_user_id(request)
    db.ensure_channel(user_id)
    channel = db.get_channel(user_id)

    comment = {
        "id": _new_id("cmt"),
        "videoId": video_id,
        "authorId": user_id,
        "authorName": channel["displayName"],
        "authorAvatarUrl": channel["avatarUrl"],
        "text": body.text,
        "parentId": body.parentId,
    }
    db.insert_comment(comment)
    return db.list_comments(video_id, limit=1)[0]


@app.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, request: Request):
    user_id = current_user_id(request)
    if not db.delete_comment(comment_id, user_id):
        error(403, "FORBIDDEN", "Esse comentário não é seu")
    return None


# ---------------------------------------------------------------------------
# Canal / perfil
# ---------------------------------------------------------------------------


@app.get("/channels/{channel_id}")
def get_channel_route(channel_id: str):
    channel = db.get_channel(channel_id)
    if not channel:
        error(404, "CHANNEL_NOT_FOUND", "Canal não encontrado")
    return channel


@app.patch("/channels/me")
def patch_my_channel(body: ChannelPatchRequest, request: Request):
    user_id = current_user_id(request)
    db.ensure_channel(user_id)
    fields = body.model_dump(exclude_none=True)
    db.patch_channel(user_id, fields)
    return db.get_channel(user_id)


@app.post("/channels/{channel_id}/subscribe")
def subscribe_channel(channel_id: str, body: SubscribeRequest, request: Request):
    if not db.get_channel(channel_id):
        error(404, "CHANNEL_NOT_FOUND", "Canal não encontrado")

    subscriber_id = current_user_id(request)
    if subscriber_id == channel_id:
        error(422, "CANNOT_SUBSCRIBE_SELF", "Você não pode se inscrever no seu próprio canal")

    subscriber_count = db.set_subscription(channel_id, subscriber_id, body.action)
    return {"subscriberCount": subscriber_count}


# ---------------------------------------------------------------------------
# Notificações
# ---------------------------------------------------------------------------


@app.get("/notifications")
def list_notifications_route(request: Request, unreadOnly: bool = False, cursor: str | None = None, limit: int = 20):
    user_id = current_user_id(request)
    items = db.list_notifications(user_id, unread_only=unreadOnly, limit=limit)
    return {"items": items, "nextCursor": None}


@app.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read_route(notification_id: str, request: Request):
    db.mark_notification_read(notification_id, current_user_id(request))
    return None


@app.post("/notifications/read-all", status_code=204)
def mark_all_notifications_read_route(request: Request):
    db.mark_all_notifications_read(current_user_id(request))
    return None


# ---------------------------------------------------------------------------
# Webhook do Clerk
# ---------------------------------------------------------------------------


@app.post("/webhooks/clerk")
async def clerk_webhook(request: Request):
    # TODO(python-service): verificar assinatura Svix com CLERK_WEBHOOK_SECRET
    # (ver CONTRACT.md, seção 1.2) antes de confiar no payload.
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})

    if event_type in ("user.created", "user.updated"):
        user_id = data.get("id")
        if user_id:
            existing = db.get_channel(user_id)
            db.upsert_channel(
                {
                    "id": user_id,
                    "displayName": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Novo usuário",
                    "avatarUrl": data.get("image_url"),
                    "bio": existing["bio"] if existing else "",
                    "subscriberCount": existing["subscriberCount"] if existing else 0,
                }
            )

    return {"received": True}
