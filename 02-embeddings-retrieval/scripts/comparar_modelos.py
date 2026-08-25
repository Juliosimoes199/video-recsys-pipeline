"""
Compara uma versão nova do modelo contra a versão "atual" (produção),
usando Recall@K/NDCG@K — o critério objetivo pra decidir se vale promover.

Uso:
    python scripts/comparar_modelos.py <versao_nova> [--k 10]

Sai com código 0 se a versão nova é igual ou melhor (por NDCG@K), 1 se é
pior — pensado pra virar um check de CI. A promoção em si continua manual
(scripts/promover_modelo.py) — este script só dá o sinal objetivo.
"""

import argparse
import sys

import avaliacao
import registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("versao_nova")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    reg = registry._carregar_registry()
    versao_atual = reg["current"]

    df = avaliacao.carregar_interacoes()
    holdout = avaliacao.preparar_holdout(df)
    print(f"Holdout: {len(holdout)} usuários com pelo menos 2 interações positivas.\n")

    modelo_novo = registry.carregar_versao(args.versao_nova)
    metricas_novo = avaliacao.avaliar_modelo(modelo_novo, holdout, k=args.k)

    print(f"Versão nova   ({args.versao_nova}):")
    print(f"  Recall@{args.k}: {metricas_novo['recall_at_k']:.4f}")
    print(f"  NDCG@{args.k}:   {metricas_novo['ndcg_at_k']:.4f}")
    print(f"  Usuários avaliados: {metricas_novo['usuarios_avaliados']}\n")

    if versao_atual is None:
        print("Nenhuma versão em produção ainda — nada pra comparar.")
        print(f"Essa seria a primeira. Promover: python scripts/promover_modelo.py {args.versao_nova}")
        sys.exit(0)

    if versao_atual == args.versao_nova:
        print("Essa já é a versão em produção.")
        sys.exit(0)

    modelo_atual = registry.carregar_versao(versao_atual)
    metricas_atual = avaliacao.avaliar_modelo(modelo_atual, holdout, k=args.k)

    print(f"Versão atual (produção) ({versao_atual}):")
    print(f"  Recall@{args.k}: {metricas_atual['recall_at_k']:.4f}")
    print(f"  NDCG@{args.k}:   {metricas_atual['ndcg_at_k']:.4f}\n")

    delta_ndcg = metricas_novo["ndcg_at_k"] - metricas_atual["ndcg_at_k"]
    delta_recall = metricas_novo["recall_at_k"] - metricas_atual["recall_at_k"]

    print("=" * 50)
    print(f"Delta NDCG@{args.k}:   {delta_ndcg:+.4f}")
    print(f"Delta Recall@{args.k}: {delta_recall:+.4f}")

    if delta_ndcg >= 0:
        print(f"\n✅ A versão nova é igual ou melhor que a produção (por NDCG@{args.k}).")
        print(f"Pra promover: python scripts/promover_modelo.py {args.versao_nova}")
        sys.exit(0)
    else:
        print(f"\n❌ A versão nova é pior que a produção (por NDCG@{args.k}). Não promova ainda.")
        sys.exit(1)


if __name__ == "__main__":
    main()
