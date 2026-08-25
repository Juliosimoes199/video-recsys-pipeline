import os
import re
import sqlite3
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "videos.db"

# Configurações da API (YouTube Data API v3)
# 1. Crie um projeto em https://console.cloud.google.com/
# 2. Ative a "YouTube Data API v3"
# 3. Crie uma credencial do tipo API Key e coloque em .env (veja .env.example)
API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "YOUTUBE_API_KEY não configurada. Copie .env.example para .env e preencha a chave, "
        "ou exporte a variável de ambiente diretamente."
    )
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def parse_duracao_iso8601(duracao):
    """Converte 'PT1M30S' em segundos."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracao)
    horas, minutos, segundos = match.groups()
    return int(horas or 0) * 3600 + int(minutos or 0) * 60 + int(segundos or 0)


def buscar_shorts(query, max_resultados=10):
    params_busca = {
        "key": API_KEY,
        "q": query,
        "type": "video",
        "videoDuration": "short",  # a API só filtra < 4min, o corte real de 60s é feito abaixo
        "part": "snippet",
        "maxResults": max_resultados,
        "safeSearch": "moderate",
    }
    resposta = requests.get(SEARCH_URL, params=params_busca)
    resposta.raise_for_status()
    ids = [item["id"]["videoId"] for item in resposta.json().get("items", [])]

    if not ids:
        return []

    params_detalhes = {
        "key": API_KEY,
        "id": ",".join(ids),
        "part": "contentDetails,snippet",
    }
    resposta2 = requests.get(VIDEOS_URL, params=params_detalhes)
    resposta2.raise_for_status()

    videos = []
    for item in resposta2.json().get("items", []):
        duracao = parse_duracao_iso8601(item["contentDetails"]["duration"])
        if duracao <= 60:  # filtro real de Shorts
            videos.append({
                "id": item["id"],
                "titulo": item["snippet"]["title"],
                "duracao": duracao,
            })
    return videos


def salvar_no_banco(videos, termo_busca):
    """Salva os vídeos encontrados no SQLite local, usando o ID do YouTube como chave."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            titulo TEXT,
            duracao INTEGER,
            termo_busca TEXT,
            url TEXT,
            salvo_em TEXT
        )
    """)
    agora = datetime.datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        """INSERT OR IGNORE INTO videos (id, titulo, duracao, termo_busca, url, salvo_em)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (v["id"], v["titulo"], v["duracao"], termo_busca,
             f"https://www.youtube.com/watch?v={v['id']}", agora)
            for v in videos
        ],
    )
    conn.commit()
    conn.close()
