import React from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Loader2 } from 'lucide-react'

export const ProtectedRoute: React.FC = () => {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-obsidian flex flex-col items-center justify-center space-y-4 text-ivory">
        <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
        <span className="text-xs uppercase tracking-widest text-secondary-text font-medium">
          Verifying Identity & Security Tokens...
        </span>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
