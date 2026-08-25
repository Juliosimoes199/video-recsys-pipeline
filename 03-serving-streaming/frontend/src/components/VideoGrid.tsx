import type { Video } from '../types'
import { VideoCard } from './VideoCard'

function SkeletonCard() {
  return (
    <div className="animate-pulse">
      <div className="aspect-video w-full rounded-xl bg-[var(--bg-elevated)]" />
      <div className="mt-3 flex gap-3">
        <div className="h-9 w-9 shrink-0 rounded-full bg-[var(--bg-elevated)]" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-4/5 rounded bg-[var(--bg-elevated)]" />
          <div className="h-3 w-3/5 rounded bg-[var(--bg-elevated)]" />
        </div>
      </div>
    </div>
  )
}

interface VideoGridProps {
  videos: Video[]
  isLoading?: boolean
  emptyMessage?: string
}

export function VideoGrid({ videos, isLoading, emptyMessage }: VideoGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (videos.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-[var(--text-muted)]">
        {emptyMessage ?? 'Nenhum vídeo encontrado.'}
      </p>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} />
      ))}
    </div>
  )
}
