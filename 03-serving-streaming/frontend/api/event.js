import { neon } from '@neondatabase/serverless'

const TIPOS_VALIDOS = new Set(['like', 'unlike', 'dislike', 'undislike', 'play', 'watch'])

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'method not allowed' })
    return
  }

  const { sessionId, videoId, eventType, watchSeconds } = req.body ?? {}

  if (!sessionId || !videoId || !TIPOS_VALIDOS.has(eventType)) {
    res.status(400).json({ error: 'payload inválido' })
    return
  }

  try {
    const sql = neon(process.env.DATABASE_URL)

    await sql`
      CREATE TABLE IF NOT EXISTS events (
        id BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        video_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        watch_seconds REAL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `

    await sql`
      INSERT INTO events (session_id, video_id, event_type, watch_seconds)
      VALUES (${sessionId}, ${videoId}, ${eventType}, ${watchSeconds ?? null})
    `
    res.status(200).json({ ok: true })
  } catch (erro) {
    res.status(500).json({ error: String(erro) })
  }
}
