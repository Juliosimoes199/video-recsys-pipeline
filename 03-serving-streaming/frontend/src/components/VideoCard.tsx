import { Link } from 'react-router-dom'
import type { Video } from '../types'
import { formatDuration, formatRelativeTime, formatViews } from '../lib/format'

export function VideoCard({ video }: { video: Video }) {
  return (
    <Link to={`/watch/${video.id}`} className="group block">
      <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-[var(--bg-elevated)]">
        {video.thumbnailUrl ? (
          <img
            src={video.thumbnailUrl}
            alt={video.title}
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-[var(--text-muted)]">
            {video.status === 'processing' || video.status === 'uploading'
              ? 'Processando...'
              : 'Sem miniatura'}
          </div>
        )}
        {video.durationSeconds > 0 && (
          <span className="absolute bottom-1 right-1 rounded bg-black/80 px-1.5 py-0.5 text-xs font-medium">
            {formatDuration(video.durationSeconds)}
          </span>
        )}
        {video.source === 'youtube' && (
          <span className="absolute bottom-1 left-1 rounded bg-black/80 px-1.5 py-0.5 text-xs font-medium">
            YouTube
          </span>
        )}
      </div>

      <div className="mt-3 flex gap-3">
        {video.channel.avatarUrl ? (
          <img src={video.channel.avatarUrl} alt="" className="h-9 w-9 shrink-0 rounded-full" />
        ) : (
          <div className="h-9 w-9 shrink-0 rounded-full bg-[var(--bg-hover)]" />
        )}
        <div className="min-w-0">
          <h3 className="line-clamp-2 text-sm font-medium text-[var(--text)]">{video.title}</h3>
          <p className="mt-1 truncate text-xs text-[var(--text-muted)]">{video.channel.displayName}</p>
          <p className="truncate text-xs text-[var(--text-muted)]">
            {formatViews(video.viewCount)} visualizações · {formatRelativeTime(video.createdAt)}
          </p>
        </div>
      </div>
    </Link>
  )
}
