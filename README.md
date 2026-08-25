# Video RecSys Pipeline

[![Avaliar modelo de retrieval](https://github.com/Juliosimoes199/video-recsys-pipeline/actions/workflows/avaliar-modelo.yml/badge.svg)](https://github.com/Juliosimoes199/video-recsys-pipeline/actions/workflows/avaliar-modelo.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pipeline de ponta a ponta de um sistema de recomendação de vídeos curtos:
coleta de dados, compreensão multimodal, embeddings de vídeo, um modelo de
retrieval de duas torres, e uma infraestrutura de streaming adaptativo real
(HLS) com um feed de recomendação estilo Reels/TikTok.

Projeto pessoal — cada estágio roda de forma independente, mas juntos
formam o fluxo completo: **dado bruto → entendimento → recomendação →
produto**.

## Arquitetura

```
Estágio 1                Estágio 2                    Estágio 3
Coleta & Visão      →     Embeddings & Retrieval  →    Serving & Streaming
────────────────          ──────────────────────       ────────────────────
YouTube Data API v3        VideoMAE (16 frames/vídeo)    FastAPI + Postgres + MinIO
Florence-2 (VLM)           → embedding 768d               HLS adaptativo (ffmpeg)
SQLite                     Two-tower retrieval            Feed estilo Reels
Flask (busca)               (TensorFlow)                  Deploy: Vercel
```

| Estágio | Diretório | O que faz |
|---|---|---|
| 1 — Coleta & Compreensão Visual | [`01-data-collection/`](01-data-collection/) | busca vídeos no YouTube, salva num SQLite, gera legenda visual de cada thumbnail com um VLM (Florence-2) |
| 2 — Embeddings & Retrieval | [`02-embeddings-retrieval/`](02-embeddings-retrieval/) | extrai embeddings de vídeo (VideoMAE) e treina um modelo de retrieval de duas torres |
| 3 — Serving & Streaming | [`03-serving-streaming/`](03-serving-streaming/) | backend de streaming adaptativo (HLS) + feed de recomendação em produção |

Cada diretório tem seu próprio README com detalhes de setup e as decisões
técnicas específicas daquele estágio.

## Demo ao vivo

O feed de recomendação (Estágio 2 servindo no Estágio 3) está publicado e
funcional: **[frontend-iota-eight-95.vercel.app](https://frontend-iota-eight-95.vercel.app/)**
(exige login) — curta alguns vídeos e o feed se
adapta em tempo real por similaridade de embeddings de vídeo.

## Destaques técnicos

- **Streaming adaptativo real**: transcodificação multi-rendition
  (480p/720p/1080p) num único passe de ffmpeg, com lógica de no-upscale
  (nunca gera uma rendition maior que o vídeo original).
- **Compreensão multimodal em duas camadas**: legendagem visual leve via
  thumbnail (Florence-2, Estágio 1) e embeddings espaço-temporais pesados
  via frames reais (VideoMAE, Estágio 2) — cada um resolvendo um problema
  diferente com o custo computacional certo pra cada um.
- **Modelo de retrieval versionado**: nenhum modelo treinado fica preso na
  memória de um notebook — cada versão é salva, registrada e promovida a
  "produção" de forma explícita e reversível (ver
  [`02-embeddings-retrieval/README.md`](02-embeddings-retrieval/README.md)).
- **Diagnóstico honesto de limitações**: o modelo de retrieval atual tem
  overfitting severo em dados sintéticos — documentado e explicado dentro
  do próprio notebook, não escondido.

## Limitações conhecidas

- O modelo de retrieval (Estágio 2) foi treinado com **interações
  sintéticas**, não uso real — ver
  [`02-embeddings-retrieval/README.md`](02-embeddings-retrieval/README.md#limitações-conhecidas-importante)
  pra detalhes e o plano pra substituir por dados reais.
- O Estágio 3 já coleta esses dados reais (curtidas, "não gostei", tempo de
  visualização por usuário) — é o próximo passo natural pra retreinar o
  modelo do Estágio 2 com sinal de verdade.
- `video-service` (Estágio 3) ainda não valida a assinatura do webhook do
  Clerk — funcional, mas não hardened pra produção real.
- Sem testes automatizados no Estágio 1/3 ainda — o único CI hoje é a
  avaliação automática de modelos de retrieval (ver "Contribuindo").

## Contribuindo

Este projeto é open source e está aberto a contribuições — de correções
pequenas a propostas de modelos de retrieval novos, especialmente de
outros devs do mercado angolano. Toda proposta de modelo novo é validada
automaticamente por CI (Recall@10/NDCG@10 contra a versão em produção,
sem intervenção manual) antes de qualquer decisão de promoção — ver
[`CONTRIBUTING.md`](CONTRIBUTING.md) pro fluxo completo.

## Como rodar

Cada estágio tem instruções detalhadas no seu próprio README. Resumo:

```bash
# Estágio 1 — coleta + visão
cd 01-data-collection && pip install -r requirements.txt
cp .env.example .env  # preencha YOUTUBE_API_KEY
python novo.py "seu termo de busca"

# Estágio 2 — embeddings + retrieval
cd ../02-embeddings-retrieval && pip install -r requirements.txt
jupyter notebook notebooks/01_extrair_embeddings_videomae.ipynb
python scripts/exportar_para_frontend.py  # gera os dados que o Estágio 3 consome

# Estágio 3 — streaming completo (Docker) ou só o feed de recomendação (Vercel)
cd ../03-serving-streaming && docker compose up --build
```

## Autor

Julio César Ngoma Simões — [LinkedIn](https://www.linkedin.com/in/j%C3%BAlio-c%C3%A9sar-1088a82b9/) · [GitHub](https://github.com/Juliosimoes199)
