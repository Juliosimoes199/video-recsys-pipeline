import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '../lib/api'
import type { Comment, Paginated } from '../types'

export function useComments(videoId: string | undefined) {
  const api = useApiClient()

  return useQuery({
    queryKey: ['comments', videoId],
    queryFn: async () => {
      const { data } = await api.get<Paginated<Comment>>(`/videos/${videoId}/comments`, {
        params: { limit: 50 },
      })
      return data
    },
    enabled: !!videoId,
  })
}

export function useAddComment(videoId: string | undefined) {
  const api = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (text: string) => {
      const { data } = await api.post<Comment>(`/videos/${videoId}/comments`, { text })
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', videoId] })
    },
  })
}
