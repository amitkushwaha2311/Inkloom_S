import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from '@/api/client'
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
  createWorkspace: (data: { name: string; description?: string }) => Promise<Workspace>
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

  // selectWorkspace: fetch workspace detail and set it as active.
  // The backend GET /workspaces/:id returns WorkspaceResponse (same shape as
  // list items) without members/current_user_role — treat it as WorkspaceDetail
  // so the UI has a valid activeWorkspace object.
  const selectWorkspace = async (workspaceId: string) => {
    try {
      const detail = await api.workspaces.get(workspaceId)
      setActiveWorkspace(detail)
      api.setActiveWorkspaceId(workspaceId)
    } catch (err: any) {
      // If the saved workspace is inaccessible (deleted / membership revoked),
      // clear it so we don't block the UI.
      if (err.status === 403 || err.status === 404) {
        api.setActiveWorkspaceId(null)
        setActiveWorkspace(null)
      } else {
        setError(err.message)
      }
    }
  }

  const refreshWorkspaces = async () => {
    if (!api.isAuthenticated()) return
    try {
      const res = await api.workspaces.list()
      const list = res.items || []
      setWorkspaces(list)

      if (list.length === 0) {
        // User has no workspaces yet — show the empty / create state.
        setActiveWorkspace(null)
        api.setActiveWorkspaceId(null)
        return
      }

      // Prefer the previously selected workspace if it's still accessible.
      const savedId = api.getActiveWorkspaceId()
      const isValidSaved = savedId ? list.some((w) => w.id === savedId) : false
      const targetId = isValidSaved ? savedId! : list[0].id

      await selectWorkspace(targetId)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const createWorkspace = async (data: { name: string; description?: string }): Promise<Workspace> => {
    const created = await api.workspaces.create(data)
    // Refresh the full list so workspaces state stays in sync, then select the new one.
    await refreshWorkspaces()
    await selectWorkspace(created.id)
    return created
  }

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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
        createWorkspace,
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
