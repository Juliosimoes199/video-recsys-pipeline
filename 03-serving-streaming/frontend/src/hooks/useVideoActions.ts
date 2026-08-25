import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '../lib/api'

type LikeAction = 'like' | 'unlike' | 'dislike' | 'undislike'

export function useRegisterView(videoId: string | undefined) {
  const api = useApiClient()

  return useMutation({
    mutationFn: async () => {
      await api.post(`/videos/${videoId}/view`)
    },
  })
}

export function useLikeVideo(videoId: string | undefined) {
  const api = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (action: LikeAction) => {
      await api.post(`/videos/${videoId}/like`, { action })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['video', videoId] }),
  })
}
