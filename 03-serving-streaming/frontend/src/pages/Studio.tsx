import { Link } from 'react-router-dom'
import { useMyVideos } from '../hooks/useChannel'
import { formatRelativeTime, formatViews } from '../lib/format'
import type { VideoStatus } from '../types'

const STATUS_LABEL: Record<VideoStatus, string> = {
  uploading: 'Enviando',
  processing: 'Processando',
  ready: 'Publicado',
  failed: 'Falhou',
}

const STATUS_COLOR: Record<VideoStatus, string> = {
  uploading: 'text-yellow-400',
  processing: 'text-yellow-400',
  ready: 'text-green-400',
  failed: 'text-red-400',
}

export function Studio() {
  const { data, isLoading } = useMyVideos()
  const videos = data?.items ?? []

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Seus vídeos</h1>
        <Link to="/upload" className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-black">
          Enviar vídeo
        </Link>
      </div>

      {isLoading && <p className="text-sm text-[var(--text-muted)]">Carregando...</p>}

      {!isLoading && videos.length === 0 && (
        <p className="text-sm text-[var(--text-muted)]">Você ainda não enviou nenhum vídeo.</p>
      )}

      <div className="divide-y divide-[var(--border)]">
        {videos.map((video) => (
          <Link
            key={video.id}
            to={`/watch/${video.id}`}
            className="flex items-center gap-4 py-3 hover:bg-[var(--bg-elevated)]"
          >
            <div className="h-16 w-28 shrink-0 overflow-hidden rounded-lg bg-[var(--bg-elevated)]">
              {video.thumbnailUrl && (
                <img src={video.thumbnailUrl} alt="" className="h-full w-full object-cover" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{video.title}</p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                {formatViews(video.viewCount)} visualizações · {formatRelativeTime(video.createdAt)}
              </p>
            </div>
            <span className={`shrink-0 text-xs font-medium ${STATUS_COLOR[video.status]}`}>
              {STATUS_LABEL[video.status]}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
