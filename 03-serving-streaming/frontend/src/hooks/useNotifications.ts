import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import { useApiClient } from '../lib/api'
import type { AppNotification, Paginated } from '../types'

export function useNotifications() {
  const api = useApiClient()
  const { isSignedIn } = useAuth()

  return useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const { data } = await api.get<Paginated<AppNotification>>('/notifications', {
        params: { limit: 20 },
      })
      return data
    },
    enabled: !!isSignedIn,
    refetchInterval: 15000,
  })
}

export function useMarkNotificationRead() {
  const api = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (notificationId: string) => {
      await api.post(`/notifications/${notificationId}/read`)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useMarkAllNotificationsRead() {
  const api = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      await api.post('/notifications/read-all')
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
