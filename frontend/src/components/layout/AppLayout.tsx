import React, { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import {
  Shield,
  LayoutDashboard,
  FileCheck,
  FileText,
  Database,
  Layers,
  Clock,
  BarChart3,
  Settings,
  LogOut,
  ChevronDown,
  Plus,
  Menu,
  X,
  Building2,
  User as UserIcon,
} from 'lucide-react'
import { api } from '@/api/client'

export const AppLayout: React.FC = () => {
  const { user, workspaces, activeWorkspace, selectWorkspace, refreshWorkspaces, logout } =
    useAuth()
  const navigate = useNavigate()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false)
  const [createWsModalOpen, setCreateWsModalOpen] = useState(false)
  const [newWsName, setNewWsName] = useState('')
  const [newWsDesc, setNewWsDesc] = useState('')
  const [creatingWs, setCreatingWs] = useState(false)

  const navItems = [
    { label: 'Overview', to: '/app', icon: <LayoutDashboard className="w-4 h-4" /> },
    { label: 'Brand Policies', to: '/app/policies', icon: <FileCheck className="w-4 h-4" /> },
    { label: 'Submissions', to: '/app/submissions', icon: <FileText className="w-4 h-4" /> },
    { label: 'Evidence & Claims', to: '/app/evidence', icon: <Database className="w-4 h-4" /> },
    { label: 'Unified Review', to: '/app/reviews', icon: <Layers className="w-4 h-4" /> },
    { label: 'Audit Trail', to: '/app/audit', icon: <Clock className="w-4 h-4" /> },
    { label: 'Analytics', to: '/app/analytics', icon: <BarChart3 className="w-4 h-4" /> },
    { label: 'Settings', to: '/app/settings', icon: <Settings className="w-4 h-4" /> },
  ]

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newWsName.trim()) return
    setCreatingWs(true)
    try {
      const created = await api.workspaces.create({
        name: newWsName.trim(),
        description: newWsDesc.trim() || undefined,
      })
      await refreshWorkspaces()
      await selectWorkspace(created.id)
      setCreateWsModalOpen(false)
      setNewWsName('')
      setNewWsDesc('')
    } catch (err: any) {
      alert(err.message || 'Failed to create workspace')
    } finally {
      setCreatingWs(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-obsidian text-ivory flex flex-col md:flex-row font-body">
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex w-64 bg-charcoal border-r border-border-dark flex-col justify-between p-4 shrink-0 select-none">
        <div className="space-y-6">
          {/* Brand header */}
          <Link to="/" className="flex items-center space-x-2.5 px-3 py-2 cursor-pointer">
            <div className="w-7 h-7 rounded-lg bg-copper flex items-center justify-center text-white">
              <Shield className="w-4 h-4" />
            </div>
            <div className="flex flex-col text-left">
              <span className="font-serif text-lg tracking-tight font-bold text-paper-white leading-none">
                Inkloom
              </span>
              <span className="text-[9px] uppercase tracking-widest text-secondary-text font-medium">
                Sentinel Console
              </span>
            </div>
          </Link>

          {/* Workspace Switcher */}
          <div className="relative">
            <button
              onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
              className="w-full p-2.5 rounded-xl bg-obsidian/70 border border-border-dark hover:border-copper/40 transition-colors flex items-center justify-between text-left text-xs text-ivory cursor-pointer"
            >
              <div className="flex items-center space-x-2.5 truncate">
                <Building2 className="w-4 h-4 text-copper-highlight shrink-0" />
                <div className="truncate">
                  <div className="font-semibold text-paper-white truncate">
                    {activeWorkspace ? activeWorkspace.name : 'Select Workspace'}
                  </div>
                  <div className="text-[10px] text-secondary-text uppercase tracking-wider">
                    {activeWorkspace?.current_user_role || 'Workspace'}
                  </div>
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-secondary-text shrink-0" />
            </button>

            {/* Dropdown Menu */}
            {workspaceDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-1.5 p-1.5 rounded-xl bg-charcoal border border-border-dark shadow-2xl z-50 space-y-1">
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
                  Your Workspaces
                </div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      selectWorkspace(ws.id)
                      setWorkspaceDropdownOpen(false)
                    }}
                    className={`w-full px-2.5 py-1.5 rounded-lg text-left text-xs truncate transition-colors flex items-center justify-between cursor-pointer ${
                      activeWorkspace?.id === ws.id
                        ? 'bg-copper text-white font-medium'
                        : 'text-ivory/80 hover:bg-white/5'
                    }`}
                  >
                    <span className="truncate">{ws.name}</span>
                  </button>
                ))}
                <button
                  onClick={() => {
                    setWorkspaceDropdownOpen(false)
                    setCreateWsModalOpen(true)
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg text-left text-xs text-copper-highlight hover:bg-copper/10 font-medium flex items-center space-x-1.5 border-t border-border-dark pt-2 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Workspace</span>
                </button>
              </div>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/app'}
                className={({ isActive }) =>
                  `w-full px-3 py-2.5 rounded-xl text-xs font-medium flex items-center space-x-3 transition-colors ${
                    isActive
                      ? 'bg-copper/20 text-copper-highlight font-semibold border-l-2 border-copper'
                      : 'text-ivory/70 hover:text-white hover:bg-white/5'
                  }`
                }
              >
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* User Card & Logout */}
        <div className="pt-4 border-t border-border-dark space-y-3">
          <div className="flex items-center space-x-3 px-2">
            <div className="w-8 h-8 rounded-full bg-surface-secondary border border-border-dark flex items-center justify-center text-xs font-semibold text-paper-white">
              <UserIcon className="w-4 h-4 text-secondary-text" />
            </div>
            <div className="truncate text-left text-xs">
              <div className="font-medium text-paper-white truncate">
                {user?.full_name || 'Authenticated User'}
              </div>
              <div className="text-[10px] text-secondary-text truncate">{user?.email}</div>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 rounded-xl text-left text-xs text-secondary-text hover:text-red-400 hover:bg-red-500/10 transition-colors flex items-center space-x-2.5 cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-charcoal border-b border-border-dark">
        <Link to="/" className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded bg-copper flex items-center justify-center text-white">
            <Shield className="w-3.5 h-3.5" />
          </div>
          <span className="font-serif text-base font-bold text-paper-white">Inkloom Sentinel</span>
        </Link>
        <button
          onClick={() => setMobileNavOpen(!mobileNavOpen)}
          className="p-1.5 text-ivory hover:text-white"
        >
          {mobileNavOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-obsidian/95 backdrop-blur-xl p-6 flex flex-col justify-between">
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-border-dark pb-4">
              <div className="text-sm font-semibold text-paper-white">
                {activeWorkspace ? activeWorkspace.name : 'Inkloom Console'}
              </div>
              <button onClick={() => setMobileNavOpen(false)}>
                <X className="w-6 h-6 text-ivory" />
              </button>
            </div>

            <nav className="space-y-2">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/app'}
                  onClick={() => setMobileNavOpen(false)}
                  className={({ isActive }) =>
                    `w-full px-4 py-3 rounded-xl text-sm font-medium flex items-center space-x-3 ${
                      isActive ? 'bg-copper text-white' : 'text-ivory/80 hover:bg-white/5'
                    }`
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <button
            onClick={handleLogout}
            className="w-full py-3 rounded-xl text-center text-sm font-semibold text-red-400 bg-red-500/10"
          >
            Sign Out
          </button>
        </div>
      )}

      {/* Main Content Viewport */}
      <main className="flex-1 overflow-y-auto bg-obsidian p-6 md:p-10 text-left">
        <div className="max-w-7xl mx-auto space-y-8">
          <Outlet />
        </div>
      </main>

      {/* Create Workspace Modal */}
      {createWsModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-charcoal border border-border-dark p-6 sm:p-8 rounded-3xl space-y-6 text-left shadow-2xl">
            <div className="space-y-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-copper-highlight">
                New Tenant
              </span>
              <h2 className="text-xl font-serif text-paper-white">Create Brand Workspace</h2>
              <p className="text-xs text-secondary-text">
                Workspaces isolate policies, submissions, and audit logs.
              </p>
            </div>

            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Acme Health Brand Governance"
                  className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Description (Optional)
                </label>
                <textarea
                  value={newWsDesc}
                  onChange={(e) => setNewWsDesc(e.target.value)}
                  placeholder="Primary workspace for consumer product packaging guidelines."
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setCreateWsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {creatingWs ? 'Creating...' : 'Create Workspace'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
