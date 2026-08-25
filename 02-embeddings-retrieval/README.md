# Estágio 2 — Embeddings & Retrieval

Transforma o catálogo de vídeos do Estágio 1 em embeddings de vídeo
(VideoMAE) e treina um modelo de retrieval de duas torres (two-tower) pra
ranquear vídeos por relevância pra cada usuário.

## O que tem aqui

| Item | Papel |
|---|---|
| `notebooks/01_extrair_embeddings_videomae.ipynb` | gera um embedding de 768-dim por vídeo a partir de 16 frames reais (`MCG-NJU/videomae-base`) |
| `notebooks/02_treinar_modelo_retrieval.ipynb` | treina o modelo two-tower e salva versões no registro de modelos |
| `scripts/registry.py` | biblioteca de versionamento de modelo (salvar, listar, carregar) |
| `scripts/promover_modelo.py` | troca qual versão do modelo está "em produção" |
| `models/` | modelos treinados, versionados — `registry.json` diz qual está ativa |
| `videos.csv` | saída do Estágio 1 (entrada deste estágio) |

## Como rodar

```bash
pip install -r requirements.txt
jupyter notebook notebooks/01_extrair_embeddings_videomae.ipynb
jupyter notebook notebooks/02_treinar_modelo_retrieval.ipynb
```

## Versionamento de modelo — como treinar e substituir

Hoje, o notebook original **não salvava o modelo em disco nenhuma vez** —
ele só existia na memória da sessão do Jupyter, e sumia ao reiniciar o
kernel. O `scripts/registry.py` resolve isso com um esquema simples:

1. **Toda vez que você treina**, a última célula do notebook 02 chama
   `registry.salvar_versao(...)`, que grava as duas torres, o catálogo de
   embeddings pré-computado e as métricas de treino numa pasta nova
   (`models/two_tower/v_AAAA-MM-DD_HHMM/`) — **sem apagar as versões
   anteriores** e **sem promover automaticamente a produção**.
2. **Você compara as versões** antes de decidir:
   ```bash
   python scripts/promover_modelo.py --listar
   ```
3. **Promove a que quiser** ficar ativa:
   ```bash
   python scripts/promover_modelo.py v_2026-09-10_1420
   ```
4. **Qualquer código consumidor** — o próprio notebook, ou futuramente uma
   API de recomendação — sempre lê o modelo com:
   ```python
   from scripts import registry
   modelo = registry.carregar_modelo_atual()
   ```
   Nunca aponta pra um caminho fixo. Trocar de versão é só o passo 3 acima
   — nenhum outro código muda.

Isso significa que treinar um modelo novo nunca quebra o que já está no
ar: a versão antiga continua sendo a "atual" até você promover
explicitamente a nova, depois de conferir que ela é realmente melhor.

## Limitações conhecidas (importante)

- **Dados de interação sintéticos**: o modelo é treinado sobre interações
  simuladas (15 mil usuários fictícios), não uso real. As métricas de
  treino não significam qualidade de recomendação real.
- **Overfitting severo**: AUC de treino ~0,999, AUC de validação ~0,50
  (nível de chance). Ver a seção "Limitações conhecidas" dentro do
  próprio notebook 02 pra entender por quê e o que fazer a respeito.
- **Sem métrica de retrieval**: falta Recall@K / NDCG — hoje a avaliação é
  só inspeção visual das recomendações.

O caminho mais direto pra melhorar isso de verdade é treinar com dados
reais: o Estágio 3 (`../03-serving-streaming`) já grava curtidas,
"não gostei" e tempo de visualização por usuário — é exatamente esse o
substituto natural dos dados sintéticos usados aqui.
