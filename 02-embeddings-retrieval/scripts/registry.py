"""
Registro de versões do modelo de retrieval (two-tower).

Cada vez que você treina um modelo novo, ele é salvo numa pasta própria
(`models/two_tower/<versao>/`) e listado em `models/registry.json` — mas
NUNCA fica "em produção" automaticamente. Promover uma versão pra ativa é
um passo separado e deliberado (`promover_modelo.py`), pra você poder
comparar métricas antes de trocar o que está servindo recomendações.

Quem consome o modelo (a própria notebook, ou futuramente uma API) sempre
lê "qual é a versão atual" daqui — nunca com um caminho fixo no código.
"""

import json
import datetime
import secrets
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
REGISTRY_PATH = MODELS_DIR / "registry.json"
TWO_TOWER_DIR = MODELS_DIR / "two_tower"


def _carregar_registry():
    if not REGISTRY_PATH.exists():
        return {"current": None, "versions": {}}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _salvar_registry(registry):
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def novo_nome_versao():
    """Gera um nome de versão único, ex: v_2026-08-25_211805_a1b2.

    Inclui segundos + um sufixo aleatório curto pra garantir que duas
    versões salvas em sequência rápida (ex: re-rodando a célula de treino
    duas vezes seguidas) nunca colidam e se sobrescrevam por engano.
    """
    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    sufixo = secrets.token_hex(2)
    return f"v_{agora}_{sufixo}"


def salvar_versao(
    user_tower,
    video_tower,
    catalog_embeddings,
    catalog_video_ids,
    user_embeddings,
    user_ids,
    metricas,
    notas="",
    versao=None,
):
    """
    Salva um novo modelo treinado como uma versão nova, e registra no
    registry.json. NÃO promove a versão a "atual" — isso é feito à parte,
    com promover_modelo.py, depois de você conferir as métricas.

    metricas: dict livre, ex. {"train_auc": 0.99, "val_auc": 0.51}

    user_embeddings/user_ids: vetores de TODOS os usuários conhecidos no
    treino (não só o catálogo) — pré-computados aqui pra: (1) permitir
    avaliação por Recall@K/NDCG@K (scripts/avaliacao.py) sem precisar
    guardar o LabelEncoder, e (2) servir de base pra um dia usar este
    modelo em produção via lookup direto, sem rodar TensorFlow por
    requisição (ver README deste estágio).
    """
    import numpy as np

    versao = versao or novo_nome_versao()
    pasta = TWO_TOWER_DIR / versao
    pasta.mkdir(parents=True, exist_ok=True)

    user_tower.save(pasta / "user_tower.keras")
    video_tower.save(pasta / "video_tower.keras")
    np.save(pasta / "catalog_embeddings.npy", catalog_embeddings)
    (pasta / "catalog_video_ids.json").write_text(
        json.dumps(list(catalog_video_ids), ensure_ascii=False), encoding="utf-8"
    )
    np.save(pasta / "user_embeddings.npy", user_embeddings)
    (pasta / "user_ids.json").write_text(
        json.dumps(list(user_ids), ensure_ascii=False), encoding="utf-8"
    )

    metadata = {
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "metricas": metricas,
        "notas": notas,
    }
    (pasta / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    registry = _carregar_registry()
    registry["versions"][versao] = metadata
    if registry["current"] is None:
        # primeira versão criada: promove automaticamente, senão não haveria
        # nenhuma versão "atual" pra servir
        registry["current"] = versao
    _salvar_registry(registry)

    print(f"Versão '{versao}' salva em {pasta}")
    if registry["current"] == versao:
        print("(promovida automaticamente — é a primeira versão registrada)")
    else:
        print(f"Ainda não é a versão ativa (atual: {registry['current']}).")
        print(f"Pra promover: python scripts/promover_modelo.py {versao}")
    return versao


def carregar_versao(versao, carregar_towers=False):
    """Carrega uma versão específica pelo nome.

    Por padrão só carrega os vetores pré-computados (rápido, sem precisar
    do TensorFlow) — passe carregar_towers=True se precisar rodar o
    modelo sobre usuários/vídeos novos que ainda não têm vetor salvo.
    """
    import numpy as np

    pasta = TWO_TOWER_DIR / versao
    if not pasta.exists():
        raise RuntimeError(f"Versão '{versao}' não encontrada em {pasta}")

    resultado = {
        "versao": versao,
        "catalog_embeddings": np.load(pasta / "catalog_embeddings.npy"),
        "catalog_video_ids": json.loads((pasta / "catalog_video_ids.json").read_text(encoding="utf-8")),
        "user_embeddings": np.load(pasta / "user_embeddings.npy"),
        "user_ids": json.loads((pasta / "user_ids.json").read_text(encoding="utf-8")),
    }

    if carregar_towers:
        import tensorflow as tf
        resultado["user_tower"] = tf.keras.models.load_model(pasta / "user_tower.keras")
        resultado["video_tower"] = tf.keras.models.load_model(pasta / "video_tower.keras")

    return resultado


def carregar_modelo_atual(carregar_towers=False):
    """Carrega a versão marcada como 'current' no registry."""
    registry = _carregar_registry()
    versao = registry["current"]
    if versao is None:
        raise RuntimeError("Nenhum modelo registrado ainda. Treine e salve uma versão primeiro.")
    return carregar_versao(versao, carregar_towers=carregar_towers)


def listar_versoes():
    registry = _carregar_registry()
    for nome, meta in registry["versions"].items():
        marcador = " (atual)" if nome == registry["current"] else ""
        print(f"{nome}{marcador} — {meta.get('metricas')} — {meta.get('notas', '')}")
