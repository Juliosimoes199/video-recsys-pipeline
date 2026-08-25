"""
Avaliação objetiva de qualidade de retrieval (Recall@K / NDCG@K).

Metodologia — "leave-one-out": pra cada usuário com pelo menos 2 vídeos
curtidos/assistidos de verdade (label=1) no dataset de interações, um
desses vídeos é escondido ("held-out") na hora de avaliar. Um modelo bom
deve conseguir colocar esse vídeo escondido entre as top-K recomendações
pra esse usuário, usando só o resto do histórico dele.

Limitação conhecida, documentada de propósito: hoje o held-out não é
excluído do treino (ver notebooks/02_treinar_modelo_retrieval.ipynb) — os
números absolutos de Recall@K/NDCG@K ficam levemente otimistas por causa
disso. Como a mesma metodologia se aplica a QUALQUER versão avaliada,
a comparação relativa entre "modelo atual" e "modelo novo" continua válida
— é exatamente pra isso que este módulo existe.
"""

import json
import math
import random
from pathlib import Path

DADOS_DIR = Path(__file__).resolve().parent.parent / "data"
INTERACOES_PATH = DADOS_DIR / "interacoes.csv"


def carregar_interacoes():
    import pandas as pd

    if not INTERACOES_PATH.exists():
        raise RuntimeError(
            f"{INTERACOES_PATH} não encontrado. Rode o notebook "
            "02_treinar_modelo_retrieval.ipynb até a célula que salva "
            "data/interacoes.csv antes de avaliar."
        )
    return pd.read_csv(INTERACOES_PATH)


def preparar_holdout(df_interacoes, seed=42, min_positivos=2):
    """Esconde um vídeo positivo por usuário elegível, pra usar como gabarito.

    Retorna um dict {user_id: video_id_escondido}.
    """
    rng = random.Random(seed)
    positivos_por_usuario = (
        df_interacoes[df_interacoes["label"] == 1]
        .groupby("user_id")["video_id"]
        .apply(list)
    )

    holdout = {}
    for user_id, videos in positivos_por_usuario.items():
        if len(videos) >= min_positivos:
            holdout[user_id] = rng.choice(videos)
    return holdout


def _top_k_para_usuario(user_id, user_ids, user_embeddings, catalog_video_ids, catalog_embeddings, k):
    import numpy as np

    if user_id not in user_ids:
        return None  # modelo não tem vetor pra esse usuário (não visto no treino)

    idx_usuario = user_ids.index(user_id)
    vetor_usuario = user_embeddings[idx_usuario]

    scores = catalog_embeddings @ vetor_usuario
    top_indices = np.argsort(scores)[::-1][:k]
    return [catalog_video_ids[i] for i in top_indices]


def avaliar_modelo(modelo, holdout, k=10):
    """
    modelo: dict retornado por registry.carregar_versao()/carregar_modelo_atual()
    holdout: dict {user_id: video_id_escondido}, de preparar_holdout()

    Retorna {"recall_at_k": float, "ndcg_at_k": float, "usuarios_avaliados": int, "k": k}
    """
    user_ids = list(modelo["user_ids"])
    user_embeddings = modelo["user_embeddings"]
    catalog_video_ids = list(modelo["catalog_video_ids"])
    catalog_embeddings = modelo["catalog_embeddings"]

    recalls = []
    ndcgs = []

    for user_id, video_escondido in holdout.items():
        top_k = _top_k_para_usuario(user_id, user_ids, user_embeddings, catalog_video_ids, catalog_embeddings, k)
        if top_k is None:
            continue  # usuário fora do vocabulário deste modelo — não conta pra nenhum dos dois lados

        if video_escondido in top_k:
            posicao = top_k.index(video_escondido)
            recalls.append(1.0)
            ndcgs.append(1.0 / math.log2(posicao + 2))  # +2 porque posição é 0-indexed
        else:
            recalls.append(0.0)
            ndcgs.append(0.0)

    if not recalls:
        raise RuntimeError(
            "Nenhum usuário do holdout tem vetor salvo neste modelo — "
            "não dá pra avaliar (user_ids incompatíveis?)."
        )

    return {
        "recall_at_k": sum(recalls) / len(recalls),
        "ndcg_at_k": sum(ndcgs) / len(ndcgs),
        "usuarios_avaliados": len(recalls),
        "k": k,
    }
