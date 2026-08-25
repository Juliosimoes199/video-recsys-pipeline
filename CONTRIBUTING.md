# Contribuindo

Obrigado pelo interesse! Este projeto está aberto a contribuições — de
correções pequenas a propostas de modelos de retrieval novos. Este guia
explica os dois fluxos.

## Configuração local

```bash
git clone https://github.com/Juliosimoes199/video-recsys-pipeline.git
cd video-recsys-pipeline

# cada estágio tem seu próprio ambiente — instale só o que for mexer
cd 01-data-collection && pip install -r requirements.txt && cd ..
cd 02-embeddings-retrieval && pip install -r requirements.txt && cd ..
cd 03-serving-streaming/frontend && npm install && cd ../..
```

Veja o README de cada estágio pra instruções detalhadas de setup e como
rodar.

## Contribuições de código (Estágio 1 e 3)

PR normal: abra uma branch, descreva o que mudou e por quê, e explique
como testou (sobretudo se mexer no `video-service` ou no `frontend`, que
não têm testes automatizados ainda — descreva o teste manual que fez).

## Propondo um modelo de retrieval novo (Estágio 2) — como funciona a validação

Esse é o fluxo mais específico do projeto, então vale explicar em
detalhe.

### 1. Treine sua versão

```bash
cd 02-embeddings-retrieval
jupyter notebook notebooks/02_treinar_modelo_retrieval.ipynb
```

Pode mudar arquitetura, hiperparâmetros, dados de entrada — o que quiser.
A única exigência é que a última célula chame `registry.salvar_versao(...)`
(já está assim no notebook) — é isso que gera a pasta versionada e os
vetores pré-computados que a avaliação precisa.

### 2. Valide localmente antes de abrir o PR

```bash
python scripts/comparar_modelos.py <nome_da_sua_versao>
```

Isso mostra Recall@10 e NDCG@10 da sua versão contra a que está em
produção agora, usando `data/interacoes.csv` (o mesmo gabarito fixo pra
todo mundo — não invente outro, é isso que garante uma comparação justa).
Metodologia: cada usuário tem uma interação escondida ("held-out"); mede
se o modelo consegue recuperar ela no top-10.

**Leia a metodologia completa em [`02-embeddings-retrieval/scripts/avaliacao.py`](02-embeddings-retrieval/scripts/avaliacao.py)**
antes de propor — tem uma limitação conhecida documentada lá (a
comparação é relativa, não um número absoluto perfeito) que é importante
entender.

### 3. Abra o PR incluindo os arquivos da versão

```bash
git add 02-embeddings-retrieval/models/two_tower/<sua_versao>/
git add 02-embeddings-retrieval/models/registry.json  # se você criou/editou algo aqui manualmente, normalmente não precisa
git commit -m "Propõe modelo <sua_versao>: <o que você mudou e por quê>"
```

Não precisa (e não deve) chamar `promover_modelo.py` — isso fica pra
depois de mergear, é uma decisão manual do mantenedor.

### 4. O CI valida automaticamente

Ao abrir o PR, um workflow (`.github/workflows/avaliar-modelo.yml`) roda
`comparar_modelos.py` pra cada versão nova detectada e publica o
resultado no resumo do job. Se a sua versão for pior que a produção
atual, o check fica vermelho — não significa que o código está quebrado,
só que ainda não superou a linha de base. PRs assim ainda podem ser
interessantes de discutir (uma arquitetura promissora que precisa de mais
ajuste, por exemplo), mas não vão ser promovidas como estão.

### 5. Se for aceito e promovido

Depois do PR mergeado, a promoção efetiva pra "produção" (o que o feed em
<https://frontend-iota-eight-95.vercel.app/> usa) é manual:

```bash
python scripts/promover_modelo.py <versao>
```

Isso é feito pelo mantenedor do repositório, não faz parte do PR.

## O que NÃO fazer

- Não edite `data/interacoes.csv` pra "melhorar" o resultado da sua
  versão — isso invalida a comparação pra todo mundo. Se você acha que o
  dataset de avaliação tem um problema real, abra uma issue discutindo
  antes.
- Não chame `promover_modelo.py` no seu PR — quem decide isso é o
  mantenedor, depois do merge.
- Não suba pesos de modelo gigantes sem necessidade — se sua arquitetura
  ficou muito maior que o baseline, mencione isso no PR pra discutirmos
  se vale o custo.

## Código de conduta

Seja respeitoso. Críticas técnicas são bem-vindas, ataques pessoais não.
