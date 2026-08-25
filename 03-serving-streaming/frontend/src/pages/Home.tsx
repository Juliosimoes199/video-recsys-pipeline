import { useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useVideoFeed } from '../hooks/useVideos'
import { VideoGrid } from '../components/VideoGrid'

export function Home() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useVideoFeed(query)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const videos = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data])

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return

    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage()
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  return (
    <div>
      {query && (
        <p className="mb-4 text-sm text-[var(--text-muted)]">
          Resultados para <span className="text-[var(--text)]">"{query}"</span>
        </p>
      )}
      <VideoGrid
        videos={videos}
        isLoading={isLoading}
        emptyMessage={query ? 'Nenhum vídeo encontrado para essa busca.' : 'Ainda não há vídeos por aqui.'}
      />
      <div ref={sentinelRef} className="h-1" />
    </div>
  )
}
