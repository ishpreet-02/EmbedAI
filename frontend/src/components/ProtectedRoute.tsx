import { Navigate, Outlet } from 'react-router-dom'

/**
 * Wraps protected routes — redirects to /login if no JWT in localStorage.
 * Fast, no API call needed (the axios interceptor handles expired tokens).
 */
export default function ProtectedRoute() {
  const token = localStorage.getItem('token')
  return token ? <Outlet /> : <Navigate to="/login" replace />
}
