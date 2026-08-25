# Estágio 3 — Serving & Streaming Adaptativo

> Este diretório é o terceiro estágio do pipeline descrito no
> [README raiz](../README.md): recebe o catálogo de vídeos + embeddings
> gerados nos Estágios 1 e 2, e serve tanto o streaming adaptativo (HLS)
> quanto um feed de recomendação estilo Reels/TikTok.

# Tube

Um clone do YouTube: contas de usuário, upload e reprodução de vídeos.

## Divisão do sistema

| Parte | Responsável | Onde |
|---|---|---|
| Frontend (React) — feed, player, upload, canal, comentários, notificações | Claude | [`frontend/`](frontend/) |
| Login, cadastro, sessão, "Entrar com Google" | Claude (via [Clerk](https://clerk.com)) | [`frontend/`](frontend/) — `@clerk/clerk-react` |
| Contrato de API entre frontend e o serviço de vídeo | Claude | [`CONTRACT.md`](CONTRACT.md) |
| Banco de dados, protocolo HLS, URLs pré-assinadas, notificações (persistência), transformação MediaConvert | Você (Python) | [`video-service/`](video-service/) — hoje é um **stub** em FastAPI |
| Orquestração com Docker | Claude | [`docker-compose.yml`](docker-compose.yml) |

O front-end nunca fala com S3/MediaConvert diretamente (exceto pelo upload em
si, que vai direto pro S3 via URL pré-assinada). Tudo o que ele sabe é a API
REST descrita em [`CONTRACT.md`](CONTRACT.md).

Autenticação é feita pelo **Clerk** (o mesmo padrão usado no
`morphospace-web`): login, cadastro, verificação de email e "Entrar com
Google" já vêm prontos via `<SignIn/>`/`<SignUp/>`. O `video-service` nunca
vê senha nenhuma — ele só valida o token de sessão do Clerk e recebe um
webhook quando um usuário é criado/atualizado (detalhes na seção 1 do
contrato).

## Setup

### 1. Crie uma conta no Clerk

1. Crie uma aplicação em [dashboard.clerk.com](https://dashboard.clerk.com).
2. Em **User & Authentication → Social Connections**, ative **Google**.
3. Em **API Keys**, copie a *Publishable key*, a *Secret key* e a *JWKS URL*.
4. Em **Webhooks**, crie um endpoint apontando para
   `http://<seu-host>:8000/webhooks/clerk` (em produção, a URL pública do seu
   `video-service`) escutando `user.created`, `user.updated`, `user.deleted`,
   e copie o *Signing Secret*.

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
# edite .env com as chaves do Clerk
```

### 3. Suba tudo

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- video-service (stub): http://localhost:8000/docs
- Console do MinIO (S3 local): http://localhost:9001 (`minioadmin` / `minioadmin`)

O stub do `video-service` já vem com 3 vídeos de demonstração (usando um
stream HLS público) — dá pra navegar no feed e assistir sem ter implementado
nada em Python ainda. Ver [`video-service/README.md`](video-service/README.md)
para o que trocar primeiro.

### Desenvolvimento com hot-reload

Pra trabalhar no frontend com hot-reload em vez de rebuildar a imagem Docker
toda hora:

```bash
docker compose up video-service postgres minio -d
cd frontend
cp .env.example .env   # ajuste VITE_CLERK_PUBLISHABLE_KEY
npm install
npm run dev
```

O Vite já faz proxy de `/api` para `http://localhost:8000` (o
`video-service` rodando via compose) — configurável em
[`frontend/vite.config.ts`](frontend/vite.config.ts).

### Popular o catálogo com vídeos do YouTube

Enquanto a base de usuários é pequena, dá pra encher o feed com vídeos do YouTube — só os
metadados vêm da API deles, o vídeo continua sendo tocado pelo player oficial embutido do
YouTube (não baixamos/rehospedamos nada — ver nota em `CONTRACT.md`, seção 2).

```bash
docker compose exec -e YOUTUBE_API_KEY=sua-chave video-service \
  python -m app.scripts.seed_youtube "termo de busca" --count 15
```

Pegue a chave em [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
(restrinja à YouTube Data API v3). Rodar de novo com o mesmo termo não duplica os vídeos já
importados.

## Estrutura

```
.
├── docker-compose.yml       # orquestra frontend + video-service + postgres + minio
├── .env.example
├── CONTRACT.md              # contrato de API entre frontend e video-service
├── frontend/                # React + Vite + TypeScript + Clerk + Tailwind
│   └── src/
│       ├── components/      # Navbar, VideoPlayer (hls.js), VideoCard, etc.
│       ├── pages/           # Home, Watch, Upload, Studio, Channel, SignIn/SignUp
│       ├── hooks/           # React Query hooks (um por área do contrato)
│       └── lib/api.ts       # cliente HTTP autenticado com o token do Clerk
└── video-service/           # SEU serviço em Python
    ├── app/main.py          # rotas do contrato
    ├── app/db.py            # persistência em Postgres (vídeos, comentários, views únicas...)
    ├── app/storage.py       # multipart upload real + setup do bucket MinIO
    ├── app/transcode.py     # FFmpeg -> HLS adaptativo, sem upscale (alternativa ao MediaConvert)
    ├── app/scripts/seed_youtube.py  # importa catálogo do YouTube (metadados só, via embed)
    └── README.md
```

## O que já funciona hoje

- Cadastro/login/logout, "Entrar com Google", sessão persistente (Clerk).
- Feed de vídeos com busca e scroll infinito.
- Página de vídeo com player HLS (`hls.js`), visualizações, like/dislike,
  comentários.
- Upload de vídeo via **multipart real** (S3/MinIO) direto do navegador, com
  barra de progresso — o backend nunca recebe o binário do vídeo.
- Pipeline completo de processamento: MinIO dispara um evento quando o
  upload termina → webhook → FFmpeg gera HLS adaptativo (sem upscale — só
  gera qualidades até a resolução real do vídeo original) + thumbnail em
  background → vídeo vira "pronto" sozinho.
- **Persistência de verdade**: vídeos, comentários, notificações e canais
  ficam no Postgres, num volume nomeado — sobrevivem a parar/subir os
  containers. Só `docker compose down -v` apaga.
- **Visualização, like/dislike e inscrição únicos por usuário**: rever o
  próprio vídeo várias vezes não soma views de novo, o dono assistindo o
  próprio vídeo nunca conta, clicar "like" repetido não infla o contador, e
  não dá pra se inscrever no próprio canal.
- "Seus vídeos" (Studio) com status de processamento.
- Página de canal com inscrição.
- Notificações (sino no topo, com contagem de não lidas).
- **Autenticação de verdade ponta a ponta**: o `video-service` valida o JWT
  do Clerk de verdade (assinatura, `iss`, `exp`) — as rotas de ação exigem
  login real, e editar/apagar vídeo ou comentário só funciona se for seu.

O que ainda falta pro `video-service` é verificar a assinatura do webhook
do Clerk (o endpoint funciona, só não confirma a origem do payload) — ver
[`video-service/README.md`](video-service/README.md).

```bash
docker compose exec -e YOUTUBE_API_KEY=sua-chave-nova video-service \
  python -m app.scripts.seed_youtube "termo de busca" --count 15
```

## Feed de recomendação (estilo Reels)

Além do app principal (que precisa do `video-service` + Postgres + MinIO no
ar), existe uma rota separada e leve — `/` (protegida por login) — que serve
como demo pública do modelo de retrieval dos Estágios 1–2, sem depender do
backend pesado:

- **`frontend/api/recommend.js`**: função serverless (Node, sem dependências)
  que calcula similaridade de cosseno entre os embeddings VideoMAE dos
  vídeos curtidos/"não gostei" e o catálogo inteiro — reaproveita
  `frontend/api/_data/catalog.json` e `embeddings.json`, exportados do
  banco do Estágio 1 + embeddings do Estágio 2.
- **`frontend/api/event.js`**: grava curtidas, "não gostei" e tempo de
  visualização por usuário (Postgres/Neon) — dados reais de uso que podem
  substituir as interações sintéticas usadas pra treinar o modelo do
  Estágio 2.
- **`frontend/src/pages/Recommended.tsx`**: feed de tela cheia com
  scroll-snap vertical (desliza pra ver o próximo vídeo) e loop automático
  — inspirado no Reels do Instagram/Facebook.

Deploy ao vivo (Vercel, gratuito): veja o link no README raiz do
repositório.
