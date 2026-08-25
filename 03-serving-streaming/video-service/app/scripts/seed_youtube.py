"""
Popula o catálogo com vídeos do YouTube — só metadados (título, descrição,
thumbnail, canal, duração) via YouTube Data API v3. O vídeo em si continua
sendo tocado pelo player oficial embutido do YouTube (ver
frontend/src/components/VideoPlayer.tsx) — a gente nunca baixa nem
rehospeda o arquivo de vídeo.

Isso é proposital, não uma limitação técnica: os Termos de Serviço da API
do YouTube não permitem usar os dados da API pra alimentar um serviço que
baixa/rehospeda o vídeo. Ver CONTRACT.md, seção 2, nota sobre
`source`/`externalId`.

Uso (de dentro do container, onde a variável DATABASE_URL já existe):

    docker compose exec video-service \\
        python -m app.scripts.seed_youtube "lofi hip hop" --count 15

A YOUTUBE_API_KEY precisa estar no ambiente (não é passada por argumento —
argumentos de linha de comando ficam no histórico do shell).

Custo de quota: cada busca (`search.list`) custa 100 unidades da cota diária
(10.000 por padrão), não importa se `--count` é 1 ou 50 — por isso o script
faz UMA busca só, pedindo até `--count` resultados numa chamada.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from .. import db

API_BASE = "https://www.googleapis.com/youtube/v3"

_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _parse_duration(iso_duration: str) -> int:
    match = _DURATION_RE.match(iso_duration)
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _get_json(path: str, params: dict) -> dict:
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="ignore")
        raise SystemExit(f"YouTube API devolveu {exc.code} em {path}: {body[:500]}")


def _search_video_ids(api_key: str, query: str, count: int) -> list[str]:
    data = _get_json(
        "search",
        {
            "key": api_key,
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": min(count, 50),
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
        },
    )
    return [item["id"]["videoId"] for item in data.get("items", [])]


def _fetch_videos(api_key: str, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    data = _get_json(
        "videos",
        {"key": api_key, "part": "snippet,contentDetails,statistics", "id": ",".join(video_ids)},
    )
    return data.get("items", [])


def _fetch_channel_avatars(api_key: str, channel_ids: set[str]) -> dict[str, str | None]:
    if not channel_ids:
        return {}
    data = _get_json(
        "channels", {"key": api_key, "part": "snippet", "id": ",".join(channel_ids)}
    )
    return {
        item["id"]: item["snippet"]["thumbnails"].get("default", {}).get("url")
        for item in data.get("items", [])
    }


def run(query: str, count: int) -> None:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Defina YOUTUBE_API_KEY no ambiente antes de rodar (não como argumento — "
            "fica no histórico do shell). Ex.: docker compose exec -e YOUTUBE_API_KEY=... "
            "video-service python -m app.scripts.seed_youtube \"...\""
        )

    print(f"Buscando até {count} vídeos pra '{query}'...")
    video_ids = _search_video_ids(api_key, query, count)
    if not video_ids:
        print("Nenhum resultado.")
        return

    videos = _fetch_videos(api_key, video_ids)
    channel_ids = {v["snippet"]["channelId"] for v in videos}
    avatars = _fetch_channel_avatars(api_key, channel_ids)

    db.init_schema()

    imported = 0
    skipped = 0
    for item in videos:
        youtube_id = item["id"]
        if db.get_video_by_external_id("youtube", youtube_id):
            skipped += 1
            continue

        snippet = item["snippet"]
        channel_id = f"yt_{snippet['channelId']}"

        db.upsert_channel(
            {
                "id": channel_id,
                "displayName": snippet["channelTitle"],
                "avatarUrl": avatars.get(snippet["channelId"]),
                "bio": "",
                "subscriberCount": 0,
            }
        )

        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )
        stats = item.get("statistics", {})

        db.insert_video(
            {
                "id": f"vid_yt_{youtube_id}",
                "ownerId": channel_id,
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "thumbnailUrl": thumbnail_url,
                "manifestUrl": None,
                "status": "ready",
                "durationSeconds": _parse_duration(item["contentDetails"]["duration"]),
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": 0,
                "dislikeCount": 0,
                "visibility": "public",
                "rawKey": None,
                "uploadId": None,
                "source": "youtube",
                "externalId": youtube_id,
            }
        )
        imported += 1
        print(f"  + {snippet['title'][:70]}")

    print(f"\nImportados: {imported}. Já existiam (pulados): {skipped}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="termo de busca no YouTube")
    parser.add_argument("--count", type=int, default=15, help="quantos vídeos importar (máx. 50)")
    args = parser.parse_args()
    run(args.query, args.count)
    sys.exit(0)
