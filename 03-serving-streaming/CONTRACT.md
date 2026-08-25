# Contrato de API — Frontend (React) ↔ Video Service (Python)

Este documento é o contrato entre o que eu construí (frontend React + autenticação via Clerk)
e o que você vai construir em Python (`video-service/`): banco de dados, protocolo HLS, URLs
pré-assinadas, notificações e a transformação via MediaConvert.

O frontend já está implementado assumindo exatamente estas rotas e formatos. Se algo aqui não
fizer sentido pra sua implementação, é só ajustar dos dois lados — isto é o ponto de partida,
não uma imposição.

Existe um **stub** funcional em `video-service/app/main.py` (FastAPI, dados em memória, sem AWS
de verdade) implementando todas as rotas abaixo com respostas falsas/mockadas, só para o
`docker compose up` já funcionar de ponta a ponta enquanto você constrói a versão real.

---

## 1. Autenticação — Clerk

O login/cadastro/OAuth do Google é 100% gerenciado pelo Clerk no frontend. O `video-service`
**não guarda senhas nem faz login** — ele só precisa:

### 1.1. Validar o token em cada requisição autenticada

O frontend manda em toda chamada:

```
Authorization: Bearer <clerk_session_token>
```

Para validar no Python:

- Busque as chaves públicas do Clerk em `https://<seu-frontend-api>.clerk.accounts.dev/.well-known/jwks.json`
  (o valor exato vem do dashboard do Clerk, em **API Keys → JWKS URL**).
- Verifique a assinatura (RS256) e valide `iss` e `exp`.
- O claim `sub` é o **ID canônico do usuário** (`clerk_user_id`) — use-o como chave estrangeira
  na sua tabela de usuários/canais.
- Bibliotecas sugeridas: `clerk-backend-api` (SDK oficial, tem `authenticate_request`) ou
  `PyJWT` + `cryptography` fazendo a verificação manual contra o JWKS (com cache).

Variáveis de ambiente que o `video-service` vai precisar:

```
CLERK_JWKS_URL=https://<seu-dominio>.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://<seu-dominio>.clerk.accounts.dev
CLERK_WEBHOOK_SECRET=<seu-segredo-de-webhook>   # para o webhook, ver 1.2
```

### 1.2. Sincronizar usuários via webhook do Clerk

Configure no dashboard do Clerk um webhook apontando para:

```
POST /webhooks/clerk
```

Eventos a assinar: `user.created`, `user.updated`, `user.deleted`.

O Clerk assina o payload com **Svix** (headers `svix-id`, `svix-timestamp`, `svix-signature`).
Verifique com a lib `svix` (Python) usando `CLERK_WEBHOOK_SECRET`. Payload de exemplo
(`user.created`/`user.updated`):

```json
{
  "type": "user.created",
  "data": {
    "id": "user_2abc...",
    "email_addresses": [{ "email_address": "ana@example.com", "id": "idn_..." }],
    "primary_email_address_id": "idn_...",
    "first_name": "Ana",
    "last_name": "Silva",
    "image_url": "https://img.clerk.com/..."
  }
}
```

Faça upsert na sua tabela `users`/`channels` usando `data.id` como `clerk_user_id`. Isso é o
que popula `channel.displayName` / `channel.avatarUrl` nas respostas de vídeo abaixo.

---

## 2. Formato geral

- Base URL configurada no frontend via `VITE_API_URL` (ex.: `http://localhost:8000/api`).
- Todas as respostas de erro seguem:
  ```json
  { "error": { "code": "VIDEO_NOT_FOUND", "message": "Vídeo não encontrado" } }
  ```
- Listagens são paginadas por cursor:
  ```json
  { "items": [...], "nextCursor": "string ou null" }
  ```

### Objeto `Video`

```jsonc
{
  "id": "vid_123",
  "ownerId": "user_2abc...",        // clerk_user_id
  "title": "Título do vídeo",
  "description": "Descrição...",
  "thumbnailUrl": "https://.../thumb.jpg",
  "manifestUrl": "https://.../master.m3u8", // null enquanto status != "ready"
  "status": "uploading | processing | ready | failed",
  "durationSeconds": 812,
  "viewCount": 1200,
  "likeCount": 45,
  "dislikeCount": 1,
  "visibility": "public | unlisted | private",
  "source": "native | youtube",
  "externalId": null,                // videoId do YouTube quando source == "youtube", senão null
  "createdAt": "2026-08-18T12:00:00Z",
  "updatedAt": "2026-08-18T12:05:00Z",
  "channel": {
    "id": "user_2abc...",
    "displayName": "Ana Silva",
    "avatarUrl": "https://img.clerk.com/..."
  }
}
```

`manifestUrl` é a URL (idealmente já pré-assinada / atrás de CloudFront) do `.m3u8` mestre do
HLS gerado pelo MediaConvert. O player do frontend (`hls.js`) espera consumir isso diretamente.

**`source`/`externalId`**: pra popular o catálogo sem depender só de uploads (ver
`video-service/scripts/seed_youtube.py`), um vídeo pode vir do YouTube em vez de upload nativo.
Nesse caso `source: "youtube"`, `externalId` é o `videoId` do YouTube, `manifestUrl` é sempre
`null` (não existe HLS nosso pra esse vídeo), e o frontend toca via **embed oficial do YouTube**
(`https://www.youtube.com/embed/{externalId}`) em vez do `hls.js`. Isso é proposital — os Termos
de Serviço da API do YouTube não permitem baixar/rehospedar o vídeo de verdade, só usar os
metadados e tocar através do player deles.

---

## 3. Rotas

### Feed / busca
```
GET /videos?query=&category=&cursor=&limit=20
→ { items: Video[], nextCursor }
```

### Detalhe do vídeo
```
GET /videos/:id
→ Video
```

### Upload — passo 1: iniciar o multipart upload

O upload usa **S3 Multipart Upload** (compatível com MinIO): o arquivo é dividido em partes
(16 MiB cada, exceto a última), e cada parte tem sua própria URL pré-assinada.

```
POST /videos/upload/presign
body: { filename: string, contentType: string, sizeBytes: number }
→ {
    videoId: "vid_123",
    uploadId: "2~AbC123...",      // UploadId do S3/MinIO
    key: "raw/vid_123/video.mp4",
    partSize: 16777216,            // 16 MiB
    parts: [
      { partNumber: 1, url: "https://minio.../raw/vid_123/video.mp4?partNumber=1&uploadId=..." },
      { partNumber: 2, url: "..." },
      ...
    ],
    expiresAt: "2026-08-18T12:30:00Z"
  }
```

O frontend faz `PUT` de cada pedaço do arquivo (`file.slice(...)`) direto na URL correspondente
— sem passar pelo `video-service`. De cada resposta, guarda o header `ETag`, que vai ser
necessário no passo 2.

### Upload — passo 2: fechar o multipart upload

```
POST /videos/:id/complete
body: {
  title: string,
  description?: string,
  visibility: "public"|"unlisted"|"private",
  parts: [{ partNumber: number, etag: string }, ...]   // coletados no passo 1
}
→ Video   (status vira "processing")
```

Isso chama `CompleteMultipartUpload` no MinIO, juntando as partes num objeto só em
`raw/:id/...`. **Não é aqui que o vídeo vira `ready`** — o MinIO dispara um evento
(`s3:ObjectCreated:CompleteMultipartUpload`) pra um webhook interno do `video-service`
(`POST /webhooks/minio`, não faz parte do contrato com o frontend), que roda o FFmpeg e só
então atualiza `status` pra `ready` (ou `failed`) e seta `manifestUrl`.

### Upload — polling de status
```
GET /videos/:id/status
→ { status: "uploading"|"processing"|"ready"|"failed", progress?: number }
```
O frontend faz polling nessa rota (a cada poucos segundos) enquanto `status !== "ready"`.
Se preferir empurrar isso via notificação (ver seção 5) em vez de polling, tudo bem — o
frontend já invalida a query de vídeo quando recebe uma notificação do tipo `video.ready`.

### Editar / apagar (dono do vídeo)
```
PATCH /videos/:id   body: { title?, description?, thumbnailUrl?, visibility? } → Video
DELETE /videos/:id  → 204
```

### Visualizações e reações
```
POST /videos/:id/view                                   → { viewCount }
POST /videos/:id/like    body: { action: "like"|"unlike"|"dislike"|"undislike" } → { likeCount, dislikeCount }
```
`POST /videos/:id/view` é idempotente por usuário: chamar de novo pro mesmo `videoId` com o
mesmo usuário autenticado não incrementa `viewCount` outra vez, e o dono do vídeo assistindo o
próprio vídeo nunca conta. O frontend pode chamar isso sempre que o player começa a tocar, sem
se preocupar em controlar "já mandei essa view?" do lado do cliente — a dedupe é responsabilidade
do servidor.

`POST /videos/:id/like` também é idempotente por usuário: um usuário só tem uma reação por
vídeo (like OU dislike, nunca as duas). Mandar `"like"` de novo quando já tinha dado like não
soma outra vez; mandar `"dislike"` quando já tinha dado like troca a reação (decrementa
`likeCount`, incrementa `dislikeCount`); mandar `"unlike"`/`"undislike"` sem ter a reação
correspondente é um no-op. O frontend não precisa controlar estado local nenhum — é só mandar
a ação que o usuário clicou, o servidor decide o que realmente muda.

### Comentários
```
GET /videos/:id/comments?cursor=&limit=20  → { items: Comment[], nextCursor }
POST /videos/:id/comments  body: { text: string, parentId?: string }  → Comment
DELETE /comments/:id       → 204
```

`Comment`: `{ id, videoId, authorId, authorName, authorAvatarUrl, text, createdAt, parentId }`

### Canal / perfil
```
GET /channels/:clerkUserId          → { id, displayName, avatarUrl, bio, subscriberCount, videos: Video[] }
PATCH /channels/me  body: { displayName?, bio?, avatarUrl? } → Channel
POST /channels/:clerkUserId/subscribe   body: { action: "subscribe"|"unsubscribe" }
```

### Notificações
```
GET  /notifications?cursor=&limit=20&unreadOnly=false → { items: Notification[], nextCursor }
POST /notifications/:id/read       → 204
POST /notifications/read-all       → 204
```

`Notification`: `{ id, type: "video.ready"|"video.failed"|"comment"|"subscriber", title, body, videoId?, read, createdAt }`

O tipo `video.ready` é o que o frontend usa para saber que pode parar de fazer polling e mostrar
o vídeo processado — dispare essa notificação quando o MediaConvert terminar o job.

Se quiser evoluir para tempo real depois, o frontend já foi pensado pra plugar um
`GET /notifications/stream` (SSE) ou WebSocket sem mudar o resto — mas por enquanto ele faz
polling simples via React Query.

---

## 4. Fluxo completo de upload (resumo)

1. Frontend → `POST /videos/upload/presign` → recebe `videoId` + `uploadId` + uma URL
   pré-assinada por parte.
2. Frontend → `PUT` de cada parte do arquivo direto nas URLs (multipart), guardando o `ETag`
   de cada resposta.
3. Frontend → `POST /videos/:id/complete` com título/descrição/visibilidade + a lista de
   `{partNumber, etag}` → `video-service` chama `CompleteMultipartUpload` no MinIO.
4. MinIO dispara o evento `s3:ObjectCreated:CompleteMultipartUpload` → webhook interno
   `POST /webhooks/minio` → `video-service` roda o FFmpeg em background (gera HLS adaptativo +
   thumbnail, sobe pra `hls/:id/` no MinIO).
5. FFmpeg termina → `status: "ready"` + `manifestUrl` + `thumbnailUrl` atualizados, e uma
   notificação `video.ready` é criada pro dono do vídeo (ou `status: "failed"` +
   `video.failed` se der erro).
6. Frontend, que estava fazendo polling em `GET /videos/:id/status`, atualiza a tela e o
   player HLS começa a consumir o `manifestUrl`.

---

## 5. O que já é real vs. o que ainda é stub (`video-service/`)

**Já é real:**
- Multipart upload de verdade contra o MinIO (`app/storage.py`) — `create_multipart_upload`,
  URL pré-assinada por parte, `complete_multipart_upload`.
- Notificação do MinIO → webhook (`POST /webhooks/minio`) → transcodificação com FFmpeg em
  background (`app/transcode.py`) → HLS adaptativo (sem upscale — as qualidades geradas nunca
  passam da resolução real do vídeo original) + thumbnail, subindo de volta pro MinIO em
  `hls/:id/`.
- CORS, bucket policy (público só em `hls/*`) e o registro do evento de notificação são
  configurados sozinhos no startup do `video-service` (`storage.ensure_bucket_ready()`).
- Persistência em Postgres (`app/db.py`) — vídeos, comentários, notificações e canais
  sobrevivem a restart/rebuild dos containers (só `docker compose down -v` apaga).
- Visualizações, reações (like/dislike) e inscrições únicas por usuário — `video_views`,
  `video_reactions` e `channel_subscriptions`, todas com chave primária composta que impede
  duplicar. Ver nota na seção 3 sobre `POST /videos/:id/view` e `POST /videos/:id/like`.
  Um usuário não pode se inscrever no próprio canal (`CANNOT_SUBSCRIBE_SELF`).
- **Validação real do JWT do Clerk** (`app/auth.py`) — assinatura RS256 verificada contra o
  JWKS público do Clerk, `iss`/`exp` validados, `sub` vira o `ownerId`/`authorId` real em todo
  o sistema. Rotas de ação (upload, comentar, curtir, editar/apagar vídeo próprio, etc.) agora
  exigem token válido de verdade (401 sem ele); `GET /videos`, `GET /videos/:id` e
  `POST /videos/:id/view` continuam funcionando sem login (visitante anônimo só não soma
  visualização, por não ter identidade pra deduplicar). Editar/apagar vídeo e apagar comentário
  também checam dono agora (403 se não for seu).

**Ainda é stub:**
- Verificação de assinatura Svix no webhook do Clerk não está feita — ver seção 1.2. O endpoint
  funciona (faz upsert do canal em `user.created`/`user.updated`), só não confirma que o payload
  realmente veio do Clerk antes de confiar nele.

Esse ponto está marcado com `# TODO(python-service):` no código.
