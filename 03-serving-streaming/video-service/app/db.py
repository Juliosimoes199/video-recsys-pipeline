"""
Persistência em Postgres.

Antes tudo vivia em `dict` no processo — um restart do container zerava
vídeos, comentários e notificações. Isso troca por Postgres (já vem
provisionado no `docker-compose.yml`, com volume nomeado `pgdata`), então
os dados sobrevivem a `docker compose stop`/`start`, restart do container,
rebuild da imagem — só um `docker compose down -v` (que apaga os volumes de
propósito) apaga os dados de verdade.

Usa psycopg (síncrono) direto — sem ORM. É pouco código de SQL, então não
compensa a complexidade extra de um ORM aqui; se o projeto crescer muito,
trocar por SQLAlchemy é uma migração local, sem mudar o contrato de fora.
"""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, kwargs={"row_factory": dict_row})


SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    avatar_url TEXT,
    bio TEXT NOT NULL DEFAULT '',
    subscriber_count INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    thumbnail_url TEXT,
    manifest_url TEXT,
    status TEXT NOT NULL,
    duration_seconds INT NOT NULL DEFAULT 0,
    view_count INT NOT NULL DEFAULT 0,
    like_count INT NOT NULL DEFAULT 0,
    dislike_count INT NOT NULL DEFAULT 0,
    visibility TEXT NOT NULL DEFAULT 'public',
    raw_key TEXT,
    upload_id TEXT,
    -- "native" (upload de verdade, HLS no MinIO) ou "youtube" (metadados
    -- importados da API do YouTube, tocado via embed oficial deles — ver
    -- scripts/seed_youtube.py). external_id é o videoId do YouTube.
    source TEXT NOT NULL DEFAULT 'native' CHECK (source IN ('native', 'youtube')),
    external_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- ADD COLUMN IF NOT EXISTS pra quem já tinha o banco criado antes dessas
-- colunas existirem (CREATE TABLE IF NOT EXISTS não altera tabela existente).
ALTER TABLE videos ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'native';
ALTER TABLE videos ADD COLUMN IF NOT EXISTS external_id TEXT;
CREATE INDEX IF NOT EXISTS idx_videos_owner ON videos(owner_id);
CREATE INDEX IF NOT EXISTS idx_videos_raw_key ON videos(raw_key);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL,
    author_name TEXT NOT NULL,
    author_avatar_url TEXT,
    text TEXT NOT NULL,
    parent_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_comments_video ON comments(video_id);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    video_id TEXT,
    read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);

-- Chave primária composta (video_id, viewer_id): é isso que garante, no
-- nível do banco, no máximo 1 visualização por usuário por vídeo. Uma
-- segunda tentativa de INSERT pro mesmo par vira um "ON CONFLICT DO
-- NOTHING" em vez de duplicar — não precisa de lógica extra pra checar
-- "será que ele já viu?" antes, o banco já rejeita.
CREATE TABLE IF NOT EXISTS video_views (
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    viewer_id TEXT NOT NULL,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, viewer_id)
);

-- Mesma ideia de video_views: (video_id, user_id) como chave primária
-- garante, no nível do banco, no máximo UMA reação por usuário por vídeo —
-- e o CHECK garante que essa reação só pode ser like OU dislike, nunca as
-- duas ao mesmo tempo (dar dislike troca a reação, não soma outra).
CREATE TABLE IF NOT EXISTS video_reactions (
    video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    reaction TEXT NOT NULL CHECK (reaction IN ('like', 'dislike')),
    reacted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (video_id, user_id)
);

-- Mesmo padrão pra inscrições: um usuário só pode estar inscrito uma vez
-- no mesmo canal.
CREATE TABLE IF NOT EXISTS channel_subscriptions (
    channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    subscriber_id TEXT NOT NULL,
    subscribed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (channel_id, subscriber_id)
);
"""


def init_schema() -> None:
    with pool.connection() as conn:
        conn.execute(SCHEMA)


VIDEO_SELECT = """
    SELECT
        v.id, v.owner_id, v.title, v.description, v.thumbnail_url, v.manifest_url,
        v.status, v.duration_seconds, v.view_count, v.like_count, v.dislike_count,
        v.visibility, v.raw_key, v.upload_id, v.source, v.external_id, v.created_at, v.updated_at,
        c.id AS channel_id, c.display_name AS channel_display_name, c.avatar_url AS channel_avatar_url
    FROM videos v
    LEFT JOIN channels c ON c.id = v.owner_id
"""


def _row_to_video(row: dict) -> dict:
    return {
        "id": row["id"],
        "ownerId": row["owner_id"],
        "title": row["title"],
        "description": row["description"],
        "thumbnailUrl": row["thumbnail_url"],
        "manifestUrl": row["manifest_url"],
        "status": row["status"],
        "durationSeconds": row["duration_seconds"],
        "viewCount": row["view_count"],
        "likeCount": row["like_count"],
        "dislikeCount": row["dislike_count"],
        "visibility": row["visibility"],
        "source": row["source"],
        "externalId": row["external_id"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
        "channel": {
            "id": row["channel_id"] or row["owner_id"],
            "displayName": row["channel_display_name"] or "Usuário",
            "avatarUrl": row["channel_avatar_url"],
        },
    }


def insert_video(video: dict) -> None:
    video = {"source": "native", "externalId": None, **video}
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO videos (id, owner_id, title, description, thumbnail_url, manifest_url,
                                 status, duration_seconds, view_count, like_count, dislike_count,
                                 visibility, raw_key, upload_id, source, external_id)
            VALUES (%(id)s, %(ownerId)s, %(title)s, %(description)s, %(thumbnailUrl)s, %(manifestUrl)s,
                    %(status)s, %(durationSeconds)s, %(viewCount)s, %(likeCount)s, %(dislikeCount)s,
                    %(visibility)s, %(rawKey)s, %(uploadId)s, %(source)s, %(externalId)s)
            """,
            video,
        )


def get_video(video_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute(f"{VIDEO_SELECT} WHERE v.id = %s", (video_id,)).fetchone()
    return _row_to_video(row) if row else None


def get_video_by_raw_key(raw_key: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute(f"{VIDEO_SELECT} WHERE v.raw_key = %s", (raw_key,)).fetchone()
    return _row_to_video(row) if row else None


def get_video_by_external_id(source: str, external_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute(
            f"{VIDEO_SELECT} WHERE v.source = %s AND v.external_id = %s", (source, external_id)
        ).fetchone()
    return _row_to_video(row) if row else None


def list_videos(query: str | None = None, owner_id: str | None = None, limit: int = 24) -> list[dict]:
    sql = VIDEO_SELECT
    conditions = []
    params: list = []
    if owner_id:
        conditions.append("v.owner_id = %s")
        params.append(owner_id)
    if query:
        conditions.append("v.title ILIKE %s")
        params.append(f"%{query}%")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY v.created_at DESC LIMIT %s"
    params.append(limit)

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_video(r) for r in rows]


def update_video(video_id: str, fields: dict) -> None:
    if not fields:
        return
    columns = {
        "title": "title",
        "description": "description",
        "thumbnailUrl": "thumbnail_url",
        "manifestUrl": "manifest_url",
        "status": "status",
        "durationSeconds": "duration_seconds",
        "visibility": "visibility",
    }
    set_clauses = []
    params: dict = {"id": video_id}
    for key, value in fields.items():
        column = columns[key]
        set_clauses.append(f"{column} = %({key})s")
        params[key] = value
    set_clauses.append("updated_at = now()")

    with pool.connection() as conn:
        conn.execute(f"UPDATE videos SET {', '.join(set_clauses)} WHERE id = %(id)s", params)


def delete_video(video_id: str) -> None:
    with pool.connection() as conn:
        conn.execute("DELETE FROM videos WHERE id = %s", (video_id,))


def set_reaction(video_id: str, user_id: str, action: str) -> dict:
    """action em "like"/"unlike"/"dislike"/"undislike". Um usuário só tem
    uma linha em video_reactions por vídeo (like OU dislike, nunca as
    duas) — dar "like" quando já tem "dislike" troca a reação (decrementa
    um contador, incrementa o outro) em vez de só somar like_count. Clicar
    "like" duas vezes seguidas não soma nada na segunda vez.
    """
    target = "like" if action in ("like", "unlike") else "dislike"
    removing = action in ("unlike", "undislike")

    with pool.connection() as conn:
        row = conn.execute(
            "SELECT reaction FROM video_reactions WHERE video_id = %s AND user_id = %s",
            (video_id, user_id),
        ).fetchone()
        current = row["reaction"] if row else None

        if removing:
            if current == target:
                conn.execute(
                    "DELETE FROM video_reactions WHERE video_id = %s AND user_id = %s",
                    (video_id, user_id),
                )
                field = f"{target}_count"
                conn.execute(f"UPDATE videos SET {field} = GREATEST(0, {field} - 1) WHERE id = %s", (video_id,))
            # current != target (ou None): não tinha essa reação mesmo -- no-op

        elif current == target:
            pass  # já estava exatamente assim -- no-op, evita contar 2x

        elif current is None:
            conn.execute(
                "INSERT INTO video_reactions (video_id, user_id, reaction) VALUES (%s, %s, %s)",
                (video_id, user_id, target),
            )
            field = f"{target}_count"
            conn.execute(f"UPDATE videos SET {field} = {field} + 1 WHERE id = %s", (video_id,))

        else:
            # trocando de like pra dislike (ou vice-versa)
            conn.execute(
                "UPDATE video_reactions SET reaction = %s, reacted_at = now() WHERE video_id = %s AND user_id = %s",
                (target, video_id, user_id),
            )
            old_field, new_field = f"{current}_count", f"{target}_count"
            conn.execute(
                f"UPDATE videos SET {old_field} = GREATEST(0, {old_field} - 1), {new_field} = {new_field} + 1 "
                "WHERE id = %s",
                (video_id,),
            )

        result = conn.execute(
            "SELECT like_count, dislike_count FROM videos WHERE id = %s", (video_id,)
        ).fetchone()
    return {"likeCount": result["like_count"], "dislikeCount": result["dislike_count"]}


def register_view(video_id: str, viewer_id: str) -> int:
    """Registra uma visualização de `viewer_id` em `video_id`. Se esse par
    já existe (o usuário já viu esse vídeo antes), não incrementa nada —
    `ON CONFLICT DO NOTHING` + checar `rowcount` é o que diferencia "view
    nova" de "view repetida" sem precisar de um SELECT explícito antes."""
    with pool.connection() as conn:
        cur = conn.execute(
            "INSERT INTO video_views (video_id, viewer_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (video_id, viewer_id),
        )
        is_new_view = cur.rowcount > 0
        if is_new_view:
            conn.execute("UPDATE videos SET view_count = view_count + 1 WHERE id = %s", (video_id,))
        row = conn.execute("SELECT view_count FROM videos WHERE id = %s", (video_id,)).fetchone()
    return row["view_count"] if row else 0


# --- comentários ---------------------------------------------------------


def list_comments(video_id: str, limit: int = 20) -> list[dict]:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT * FROM comments WHERE video_id = %s ORDER BY created_at DESC LIMIT %s",
            (video_id, limit),
        ).fetchall()
    return [_row_to_comment(r) for r in rows]


def _row_to_comment(row: dict) -> dict:
    return {
        "id": row["id"],
        "videoId": row["video_id"],
        "authorId": row["author_id"],
        "authorName": row["author_name"],
        "authorAvatarUrl": row["author_avatar_url"],
        "text": row["text"],
        "createdAt": row["created_at"].isoformat(),
        "parentId": row["parent_id"],
    }


def insert_comment(comment: dict) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO comments (id, video_id, author_id, author_name, author_avatar_url, text, parent_id)
            VALUES (%(id)s, %(videoId)s, %(authorId)s, %(authorName)s, %(authorAvatarUrl)s, %(text)s, %(parentId)s)
            """,
            comment,
        )


def delete_comment(comment_id: str, author_id: str) -> bool:
    """Só apaga se `author_id` bater com o autor do comentário. Devolve se
    apagou de verdade — usado pra decidir 204 vs 403 na rota."""
    with pool.connection() as conn:
        cur = conn.execute(
            "DELETE FROM comments WHERE id = %s AND author_id = %s", (comment_id, author_id)
        )
        deleted = cur.rowcount > 0
    return deleted


# --- canais ---------------------------------------------------------------


def ensure_channel(channel_id: str, default_display_name: str = "Usuário") -> None:
    """Cria uma linha mínima em `channels` se ainda não existir — pra quando
    alguém comenta/se inscreve antes de ter passado pelo webhook do Clerk
    (`upsert_channel`) ou pelo PATCH /channels/me."""
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO channels (id, display_name, avatar_url, bio, subscriber_count)
            VALUES (%s, %s, NULL, '', 0)
            ON CONFLICT (id) DO NOTHING
            """,
            (channel_id, default_display_name),
        )


def upsert_channel(channel: dict) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO channels (id, display_name, avatar_url, bio, subscriber_count)
            VALUES (%(id)s, %(displayName)s, %(avatarUrl)s, %(bio)s, %(subscriberCount)s)
            ON CONFLICT (id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                avatar_url = EXCLUDED.avatar_url
            """,
            channel,
        )


def get_channel(channel_id: str) -> dict | None:
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM channels WHERE id = %s", (channel_id,)).fetchone()
        if not row:
            return None
        videos = conn.execute(
            f"{VIDEO_SELECT} WHERE v.owner_id = %s AND v.visibility = 'public' ORDER BY v.created_at DESC",
            (channel_id,),
        ).fetchall()
    return {
        "id": row["id"],
        "displayName": row["display_name"],
        "avatarUrl": row["avatar_url"],
        "bio": row["bio"],
        "subscriberCount": row["subscriber_count"],
        "videos": [_row_to_video(v) for v in videos],
    }


def patch_channel(channel_id: str, fields: dict) -> None:
    columns = {"displayName": "display_name", "bio": "bio", "avatarUrl": "avatar_url"}
    set_clauses = [f"{columns[k]} = %({k})s" for k in fields]
    if not set_clauses:
        return
    params = {**fields, "id": channel_id}
    with pool.connection() as conn:
        conn.execute(f"UPDATE channels SET {', '.join(set_clauses)} WHERE id = %(id)s", params)


def set_subscription(channel_id: str, subscriber_id: str, action: str) -> int:
    """Mesmo padrão de video_views: (channel_id, subscriber_id) como chave
    primária garante no máximo 1 inscrição por usuário por canal — clicar
    "inscrever-se" várias vezes seguidas não soma de novo, e
    "cancelar inscrição" sem estar inscrito não decrementa à toa."""
    with pool.connection() as conn:
        if action == "subscribe":
            cur = conn.execute(
                "INSERT INTO channel_subscriptions (channel_id, subscriber_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (channel_id, subscriber_id),
            )
            if cur.rowcount > 0:
                conn.execute(
                    "UPDATE channels SET subscriber_count = subscriber_count + 1 WHERE id = %s",
                    (channel_id,),
                )
        else:
            cur = conn.execute(
                "DELETE FROM channel_subscriptions WHERE channel_id = %s AND subscriber_id = %s",
                (channel_id, subscriber_id),
            )
            if cur.rowcount > 0:
                conn.execute(
                    "UPDATE channels SET subscriber_count = GREATEST(0, subscriber_count - 1) WHERE id = %s",
                    (channel_id,),
                )
        row = conn.execute("SELECT subscriber_count FROM channels WHERE id = %s", (channel_id,)).fetchone()
    return row["subscriber_count"] if row else 0


# --- notificações -----------------------------------------------------------


def list_notifications(user_id: str, unread_only: bool = False, limit: int = 20) -> list[dict]:
    sql = "SELECT * FROM notifications WHERE user_id = %s"
    params: list = [user_id]
    if unread_only:
        sql += " AND read = FALSE"
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_notification(r) for r in rows]


def _row_to_notification(row: dict) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "body": row["body"],
        "videoId": row["video_id"],
        "read": row["read"],
        "createdAt": row["created_at"].isoformat(),
    }


def insert_notification(notification: dict) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO notifications (id, user_id, type, title, body, video_id, read)
            VALUES (%(id)s, %(userId)s, %(type)s, %(title)s, %(body)s, %(videoId)s, %(read)s)
            """,
            notification,
        )


def mark_notification_read(notification_id: str, user_id: str) -> None:
    # Escopado por user_id: sem isso, dava pra marcar como lida uma
    # notificação de qualquer outro usuário só sabendo o id dela.
    with pool.connection() as conn:
        conn.execute(
            "UPDATE notifications SET read = TRUE WHERE id = %s AND user_id = %s",
            (notification_id, user_id),
        )


def mark_all_notifications_read(user_id: str) -> None:
    with pool.connection() as conn:
        conn.execute("UPDATE notifications SET read = TRUE WHERE user_id = %s", (user_id,))
