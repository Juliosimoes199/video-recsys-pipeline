import type { ReactNode } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { Navigate, useLocation } from 'react-router-dom'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth()
  const location = useLocation()

  if (!isLoaded) return null

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
