"""
Troca qual versão do modelo de retrieval está "em produção".

Uso:
    python scripts/promover_modelo.py v_2026-09-10_1420
    python scripts/promover_modelo.py --listar
"""

import sys
from registry import TWO_TOWER_DIR, _carregar_registry, _salvar_registry, listar_versoes


def promover(versao):
    pasta = TWO_TOWER_DIR / versao
    if not pasta.exists():
        print(f"Versão '{versao}' não encontrada em {pasta}")
        print("\nVersões disponíveis:")
        listar_versoes()
        sys.exit(1)

    registry = _carregar_registry()
    anterior = registry["current"]
    registry["current"] = versao
    _salvar_registry(registry)

    print(f"Modelo ativo trocado: {anterior} -> {versao}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--listar":
        listar_versoes()
    else:
        promover(sys.argv[1])
