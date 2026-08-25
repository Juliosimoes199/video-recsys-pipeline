import axios, { type AxiosInstance } from 'axios'
import { useAuth } from '@clerk/clerk-react'
import { useMemo } from 'react'

const baseURL = import.meta.env.VITE_API_URL ?? '/api'

export function createApiClient(getToken: () => Promise<string | null>): AxiosInstance {
  const client = axios.create({ baseURL })

  client.interceptors.request.use(async (config) => {
    const token = await getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  return client
}

/** Axios instance authenticated with the current Clerk session token. */
export function useApiClient(): AxiosInstance {
  const { getToken } = useAuth()
  return useMemo(() => createApiClient(getToken), [getToken])
}
