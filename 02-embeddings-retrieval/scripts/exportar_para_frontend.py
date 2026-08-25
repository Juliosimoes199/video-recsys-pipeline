"""
Junta o catálogo (Estágio 1) com os embeddings VideoMAE (Estágio 2.1) e
gera os dois arquivos que o feed de recomendação (Estágio 3) consome:

  03-serving-streaming/frontend/api/_data/catalog.json
  03-serving-streaming/frontend/api/_data/embeddings.json

É a peça que liga "temos dados novos" a "o feed em produção enxerga esses
dados novos". Rode sempre que:
  - coletar vídeos novos no Estágio 1, E
  - gerar os embeddings deles no Estágio 2.1 (notebook 01)

Uso:
    python scripts/exportar_para_frontend.py
"""

import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
VIDEOS_DB = RAIZ / "01-data-collection" / "videos.db"
VIDEOS_NEW_CSV = RAIZ / "02-embeddings-retrieval" / "videos_new.csv"
DEST_DIR = RAIZ / "03-serving-streaming" / "frontend" / "api" / "_data"

FLOAT_RE = re.compile(r"-?\d+\.\d+(?:e[+-]?\d+)?")


def main():
    if not VIDEOS_NEW_CSV.exists():
        print(f"Não achei {VIDEOS_NEW_CSV}")
        print("Rode antes o notebook 01_extrair_embeddings_videomae.ipynb (Estágio 2.1).")
        sys.exit(1)

    conn = sqlite3.connect(VIDEOS_DB)
    conn.row_factory = sqlite3.Row
    meta = {
        row["id"]: {
            "id": row["id"],
            "titulo": row["titulo"],
            "duracao": row["duracao"],
            "url": row["url"],
        }
        for row in conn.execute("SELECT id, titulo, duracao, url FROM videos")
    }
    conn.close()

    catalogo = []
    embeddings = []

    with open(VIDEOS_NEW_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for linha in reader:
            video_id = linha["id"]
            if video_id not in meta:
                continue

            vetor = [float(x) for x in FLOAT_RE.findall(linha["embedding_videomae"])]
            if len(vetor) != 768:
                print(f"aviso: {video_id} tem {len(vetor)} valores, esperado 768 — pulando", file=sys.stderr)
                continue

            catalogo.append(meta[video_id])
            embeddings.append(vetor)

    assert len(catalogo) == len(embeddings)

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEST_DIR / "catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False)
    with open(DEST_DIR / "embeddings.json", "w") as f:
        json.dump(embeddings, f)

    print(f"{len(catalogo)} vídeos exportados para {DEST_DIR}")
    print("Pra ir ao ar: cd ../03-serving-streaming/frontend && vercel --prod")


if __name__ == "__main__":
    main()
