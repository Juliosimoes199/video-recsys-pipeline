import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useApiClient } from '../lib/api'
import type { Paginated, Video } from '../types'

export function useVideoFeed(query?: string) {
  const api = useApiClient()

  return useInfiniteQuery({
    queryKey: ['videos', { query: query ?? '' }],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.get<Paginated<Video>>('/videos', {
        params: { query: query || undefined, cursor: pageParam, limit: 24 },
      })
      return data
    },
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

export function useVideo(videoId: string | undefined) {
  const api = useApiClient()

  return useQuery({
    queryKey: ['video', videoId],
    queryFn: async () => {
      const { data } = await api.get<Video>(`/videos/${videoId}`)
      return data
    },
    enabled: !!videoId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'processing' || status === 'uploading' ? 4000 : false
    },
  })
}
