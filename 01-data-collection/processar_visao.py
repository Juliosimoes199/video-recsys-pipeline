import re
import sys
import sqlite3
import torch
import requests
from io import BytesIO
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

from youtube_api import DB_PATH

MODELO = "microsoft/Florence-2-base"
TAREFA = "<MORE_DETAILED_CAPTION>"


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "with", "of", "in", "on", "at", "to", "for",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
    "it", "its", "they", "their", "he", "she", "his", "her", "him", "them", "there",
    "has", "have", "had", "as", "by", "from", "into", "up", "down", "out", "over",
    "image", "shows", "showing", "shown", "background", "text", "reads", "which",
    "also", "some", "other", "front", "middle", "top", "bottom", "one", "two",
}


def migrar_schema(conn):
    colunas = [linha[1] for linha in conn.execute("PRAGMA table_info(videos)")]
    if "legenda_visual" not in colunas:
        conn.execute("ALTER TABLE videos ADD COLUMN legenda_visual TEXT")
    if "tags_visao" not in colunas:
        conn.execute("ALTER TABLE videos ADD COLUMN tags_visao TEXT")
    conn.commit()


def baixar_thumbnail(video_id):
    url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    resposta = requests.get(url, timeout=10)
    resposta.raise_for_status()
    return Image.open(BytesIO(resposta.content)).convert("RGB")


def gerar_legenda(imagem, model, processor):
    inputs = processor(text=TAREFA, images=imagem, return_tensors="pt")
    with torch.no_grad():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=128,
            num_beams=1,
        )
    texto = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    resultado = processor.post_process_generation(texto, task=TAREFA, image_size=(imagem.width, imagem.height))
    return resultado[TAREFA]


def extrair_tags(legenda, max_tags=15):
    palavras = re.findall(r"[a-zA-ZÀ-ÿ]+", legenda.lower())
    tags = []
    for palavra in palavras:
        if len(palavra) > 2 and palavra not in STOPWORDS and palavra not in tags:
            tags.append(palavra)
    return tags[:max_tags]


def videos_pendentes(conn, limite):
    linhas = conn.execute(
        "SELECT id FROM videos WHERE legenda_visual IS NULL LIMIT ?", (limite,)
    )
    return [linha[0] for linha in linhas]


if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    conn = sqlite3.connect(DB_PATH)
    migrar_schema(conn)

    ids = videos_pendentes(conn, limite)
    total_pendente = conn.execute("SELECT COUNT(*) FROM videos WHERE legenda_visual IS NULL").fetchone()[0]

    if not ids:
        print("Nenhum vídeo pendente de análise.")
        sys.exit()

    print(f"{total_pendente} vídeos pendentes no total. Processando {len(ids)} agora.")
    print(f"Carregando {MODELO}...")
    model = AutoModelForCausalLM.from_pretrained(
        MODELO, trust_remote_code=True, attn_implementation="eager", low_cpu_mem_usage=True
    )
    processor = AutoProcessor.from_pretrained(MODELO, trust_remote_code=True)

    for i, video_id in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {video_id}...", end=" ", flush=True)
        try:
            imagem = baixar_thumbnail(video_id)
            legenda = gerar_legenda(imagem, model, processor)
            tags = extrair_tags(legenda)

            conn.execute(
                "UPDATE videos SET legenda_visual = ?, tags_visao = ? WHERE id = ?",
                (legenda, ",".join(tags), video_id),
            )
            conn.commit()
            print(f"ok — tags: {', '.join(tags[:6])}...")
        except Exception as erro:
            print(f"falhou: {erro}")

    restantes = conn.execute("SELECT COUNT(*) FROM videos WHERE legenda_visual IS NULL").fetchone()[0]
    print(f"\nConcluído. Ainda faltam {restantes} vídeos — rode de novo pra continuar.")
    conn.close()
    
