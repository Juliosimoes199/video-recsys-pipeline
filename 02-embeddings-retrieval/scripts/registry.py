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
    """Gera um nome de versão único baseado na data/hora, ex: v_2026-08-25_2015"""
    return "v_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M")


def salvar_versao(user_tower, video_tower, catalog_embeddings, catalog_video_ids, metricas, notas="", versao=None):
    """
    Salva um novo modelo treinado como uma versão nova, e registra no
    registry.json. NÃO promove a versão a "atual" — isso é feito à parte,
    com promover_modelo.py, depois de você conferir as métricas.

    metricas: dict livre, ex. {"train_auc": 0.99, "val_auc": 0.51}
    """
    versao = versao or novo_nome_versao()
    pasta = TWO_TOWER_DIR / versao
    pasta.mkdir(parents=True, exist_ok=True)

    user_tower.save(pasta / "user_tower.keras")
    video_tower.save(pasta / "video_tower.keras")
    np_path = pasta / "catalog_embeddings.npy"
    import numpy as np
    np.save(np_path, catalog_embeddings)
    (pasta / "catalog_video_ids.json").write_text(
        json.dumps(list(catalog_video_ids), ensure_ascii=False), encoding="utf-8"
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


def carregar_modelo_atual():
    """Carrega a versão marcada como 'current' no registry."""
    import tensorflow as tf
    import numpy as np

    registry = _carregar_registry()
    versao = registry["current"]
    if versao is None:
        raise RuntimeError("Nenhum modelo registrado ainda. Treine e salve uma versão primeiro.")

    pasta = TWO_TOWER_DIR / versao
    user_tower = tf.keras.models.load_model(pasta / "user_tower.keras")
    catalog_embeddings = np.load(pasta / "catalog_embeddings.npy")
    catalog_video_ids = json.loads((pasta / "catalog_video_ids.json").read_text(encoding="utf-8"))
    return {
        "versao": versao,
        "user_tower": user_tower,
        "catalog_embeddings": catalog_embeddings,
        "catalog_video_ids": catalog_video_ids,
    }


def listar_versoes():
    registry = _carregar_registry()
    for nome, meta in registry["versions"].items():
        marcador = " (atual)" if nome == registry["current"] else ""
        print(f"{nome}{marcador} — {meta.get('metricas')} — {meta.get('notas', '')}")
