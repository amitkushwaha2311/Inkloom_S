import React, { createContext, useContext, useEffect, useState } from 'react'
import { api, ApiError } from '@/api/client'
import { User, Workspace, WorkspaceDetail } from '@/types/api'

interface AuthContextType {
  user: User | null
  workspaces: Workspace[]
  activeWorkspace: WorkspaceDetail | null
  loading: boolean
  error: string | null
  login: (data: { email: string; password: string }) => Promise<void>
  register: (data: { email: string; password: string; full_name: string }) => Promise<void>
  logout: () => Promise<void>
  selectWorkspace: (workspaceId: string) => Promise<void>
  refreshWorkspaces: () => Promise<void>
  refreshUser: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceDetail | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const clearError = () => setError(null)

  const refreshUser = async () => {
    if (!api.isAuthenticated()) {
      setUser(null)
      setActiveWorkspace(null)
      setLoading(false)
      return
    }

    try {
      const u = await api.auth.me()
      setUser(u)
      await refreshWorkspaces()
    } catch (err: any) {
      if (err.status === 401) {
        api.setTokens(null)
        setUser(null)
        setActiveWorkspace(null)
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  const refreshWorkspaces = async () => {
    if (!api.isAuthenticated()) return
    try {
      const res = await api.workspaces.list()
      setWorkspaces(res.items || [])

      const savedId = api.getActiveWorkspaceId()
      const targetWorkspace =
        res.items.find((w) => w.id === savedId) || res.items[0]

      if (targetWorkspace) {
        await selectWorkspace(targetWorkspace.id)
      } else {
        setActiveWorkspace(null)
        api.setActiveWorkspaceId(null)
      }
    } catch (err: any) {
      setError(err.message)
    }
  }

  const selectWorkspace = async (workspaceId: string) => {
    try {
      const detail = await api.workspaces.get(workspaceId)
      setActiveWorkspace(detail)
      api.setActiveWorkspaceId(workspaceId)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const login = async (data: { email: string; password: string }) => {
    clearError()
    setLoading(true)
    try {
      await api.auth.login(data)
      const u = await api.auth.me()
      setUser(u)
      await refreshWorkspaces()
    } catch (err: any) {
      setError(err.message || 'Login failed')
      throw err
    } finally {
      setLoading(false)
    }
  }

  const register = async (data: { email: string; password: string; full_name: string }) => {
    clearError()
    setLoading(true)
    try {
      await api.auth.register(data)
      // Automatically log in after registration
      await api.auth.login({ email: data.email, password: data.password })
      const u = await api.auth.me()
      setUser(u)
      await refreshWorkspaces()
    } catch (err: any) {
      setError(err.message || 'Registration failed')
      throw err
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    setLoading(true)
    try {
      await api.auth.logout()
    } finally {
      setUser(null)
      setActiveWorkspace(null)
      setWorkspaces([])
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshUser()
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        workspaces,
        activeWorkspace,
        loading,
        error,
        login,
        register,
        logout,
        selectWorkspace,
        refreshWorkspaces,
        refreshUser,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
