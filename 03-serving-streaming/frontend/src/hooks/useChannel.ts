import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '../lib/api'
import type { Channel, Paginated, Video } from '../types'

export function useChannel(channelId: string | undefined) {
  const api = useApiClient()

  return useQuery({
    queryKey: ['channel', channelId],
    queryFn: async () => {
      const { data } = await api.get<Channel>(`/channels/${channelId}`)
      return data
    },
    enabled: !!channelId,
  })
}

export function useMyVideos() {
  const api = useApiClient()

  return useQuery({
    queryKey: ['my-videos'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<Video>>('/videos', {
        params: { mine: true, limit: 50 },
      })
      return data
    },
  })
}

export function useSubscribe(channelId: string | undefined) {
  const api = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (action: 'subscribe' | 'unsubscribe') => {
      await api.post(`/channels/${channelId}/subscribe`, { action })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['channel', channelId] }),
  })
}
