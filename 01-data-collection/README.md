# Estágio 1 — Coleta & Compreensão Visual

Coleta vídeos curtos do YouTube via API oficial, salva num banco SQLite e gera uma
legenda visual de cada vídeo com um modelo de visão-linguagem (VLM), a partir da
thumbnail — sem baixar nenhum arquivo de vídeo.

## O que tem aqui

| Arquivo | Papel |
|---|---|
| `youtube_api.py` | busca e salva vídeos via YouTube Data API v3 (lógica compartilhada) |
| `novo.py` | script de terminal: `python novo.py <termo de busca>` |
| `servidor.py` | servidor Flask com campo de busca ao vivo |
| `banco.py` | ver/exportar o `videos.db` pra CSV |
| `processar_visao.py` | roda o Florence-2 sobre as thumbnails e grava a legenda visual no banco |
| `videos.db` | banco SQLite já populado (389 vídeos, buscados em ago/2026) |

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha YOUTUBE_API_KEY

python novo.py gatos engraçados     # busca + salva no banco
python servidor.py                  # servidor web com busca
python banco.py csv                 # exporta o banco pra CSV
python processar_visao.py 20        # gera legenda visual pra 20 vídeos pendentes
```

`processar_visao.py` é resumível: só processa vídeos onde `legenda_visual IS NULL`,
e salva (`commit`) a cada vídeo — pode parar e retomar a qualquer momento.

## Decisões que valem explicar

- **Legenda visual via thumbnail, não via frames do vídeo**: a API do YouTube não
  entrega o arquivo de vídeo, só metadados — então a análise visual roda sobre a
  thumbnail pública (`img.youtube.com/vi/{id}/...`), que não exige nenhuma
  ferramenta de download. Para o Estágio 2 (embeddings VideoMAE), que precisa de
  movimento/frames reais, a estratégia é diferente — ver `../02-embeddings-retrieval`.
- **`transformers` fixo em `4.49.0`**: o Florence-2 usa `trust_remote_code`, e
  versões mais novas da biblioteca (5.x) quebram a API interna que o código
  remoto do modelo espera.
- **`torch`/`torchvision` do mesmo índice**: instalar os dois via
  `--index-url https://download.pytorch.org/whl/cpu` evita um erro de
  incompatibilidade binária (`torchvision::nms does not exist`).
- **`num_beams=1` na geração**: a primeira tentativa usava beam search (`num_beams=3`),
  que quase esgotou a memória de uma máquina com 7,6GB de RAM. Geração gulosa
  (`num_beams=1`) resolveu sem perda perceptível de qualidade.
