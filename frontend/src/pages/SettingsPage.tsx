import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import { WorkspaceDetail, WorkspaceMember, WorkspaceRole } from '@/types/api'
import {
  Settings,
  Users,
  Shield,
  KeyRound,
  Loader2,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Building2,
  X,
} from 'lucide-react'

export const SettingsPage: React.FC = () => {
  const { activeWorkspace, user, refreshWorkspaces } = useAuth()

  // Workspace form
  const [wsName, setWsName] = useState(activeWorkspace?.name || '')
  const [wsDesc, setWsDesc] = useState(activeWorkspace?.description || '')
  const [updatingWs, setUpdatingWs] = useState(false)
  const [wsSuccessMsg, setWsSuccessMsg] = useState<string | null>(null)

  // Members
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [loadingMembers, setLoadingMembers] = useState(false)
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [newMemberEmail, setNewMemberEmail] = useState('')
  const [newMemberRole, setNewMemberRole] = useState<WorkspaceRole>('reviewer')
  const [addingMember, setAddingMember] = useState(false)

  // Password change
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [changingPass, setChangingPass] = useState(false)
  const [passSuccessMsg, setPassSuccessMsg] = useState<string | null>(null)
  const [passErrorMsg, setPassErrorMsg] = useState<string | null>(null)

  const loadMembers = async () => {
    if (!activeWorkspace) return
    setLoadingMembers(true)
    try {
      const detail = await api.workspaces.get(activeWorkspace.id)
      setMembers(detail.members || [])
      setWsName(detail.name)
      setWsDesc(detail.description || '')
    } catch {
      // Ignore
    } finally {
      setLoadingMembers(false)
    }
  }

  useEffect(() => {
    loadMembers()
  }, [activeWorkspace])

  const handleUpdateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !wsName.trim()) return
    setUpdatingWs(true)
    setWsSuccessMsg(null)
    try {
      await api.workspaces.update(activeWorkspace.id, {
        name: wsName.trim(),
        description: wsDesc.trim() || undefined,
      })
      await refreshWorkspaces()
      setWsSuccessMsg('Workspace profile updated successfully.')
    } catch (err: any) {
      alert(err.message || 'Failed to update workspace')
    } finally {
      setUpdatingWs(false)
    }
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !newMemberEmail.trim()) return
    setAddingMember(true)
    try {
      await api.workspaces.addMember(activeWorkspace.id, {
        email: newMemberEmail.trim(),
        role: newMemberRole,
      })
      setAddMemberOpen(false)
      setNewMemberEmail('')
      await loadMembers()
    } catch (err: any) {
      alert(err.message || 'Failed to add member')
    } finally {
      setAddingMember(false)
    }
  }

  const handleRemoveMember = async (memberId: string) => {
    if (!activeWorkspace) return
    if (!confirm('Are you sure you want to remove this member from the workspace?')) return
    try {
      await api.workspaces.removeMember(activeWorkspace.id, memberId)
      await loadMembers()
    } catch (err: any) {
      alert(err.message || 'Failed to remove member')
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentPassword || !newPassword) return
    if (newPassword.length < 8) {
      setPassErrorMsg('New password must be at least 8 characters long.')
      return
    }

    setChangingPass(true)
    setPassErrorMsg(null)
    setPassSuccessMsg(null)
    try {
      await api.auth.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setPassSuccessMsg('Password changed successfully.')
      setCurrentPassword('')
      setNewPassword('')
    } catch (err: any) {
      setPassErrorMsg(err.message || 'Failed to change password. Verify your current password.')
    } finally {
      setChangingPass(false)
    }
  }

  if (!activeWorkspace) {
    return (
      <div className="p-12 text-center text-secondary-text">
        Select a workspace to configure settings.
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-up max-w-5xl text-left">
      {/* Header */}
      <div className="pb-4 border-b border-border-dark space-y-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
          Tenant Administration
        </span>
        <h1 className="font-serif text-3xl text-paper-white tracking-tight">
          Workspace Settings & Security
        </h1>
        <p className="text-secondary-text text-xs">
          Manage workspace profile, multi-tenant RBAC memberships, and account credentials.
        </p>
      </div>

      {/* Workspace Profile Form */}
      <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 shadow-xl">
        <div className="flex items-center space-x-3 border-b border-border-dark pb-4">
          <Building2 className="w-5 h-5 text-copper-highlight" />
          <div>
            <h3 className="font-serif text-xl text-paper-white">Workspace Information</h3>
            <p className="text-xs text-secondary-text">
              Tenant slug: <span className="font-mono text-ivory/80">{activeWorkspace.slug}</span>
            </p>
          </div>
        </div>

        {wsSuccessMsg && (
          <div className="p-3.5 rounded-xl bg-chartreuse/10 border border-chartreuse/20 text-chartreuse text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{wsSuccessMsg}</span>
          </div>
        )}

        <form onSubmit={handleUpdateWorkspace} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
              Workspace Name
            </label>
            <input
              type="text"
              required
              value={wsName}
              onChange={(e) => setWsName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
              Description
            </label>
            <textarea
              rows={2}
              value={wsDesc}
              onChange={(e) => setWsDesc(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
            />
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={updatingWs}
              className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider cursor-pointer shadow-md"
            >
              {updatingWs ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>

      {/* Team Members & RBAC */}
      <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-border-dark pb-4">
          <div className="flex items-center space-x-3">
            <Users className="w-5 h-5 text-chartreuse" />
            <div>
              <h3 className="font-serif text-xl text-paper-white">Workspace Members & RBAC</h3>
              <p className="text-xs text-secondary-text">
                Enforces privilege hierarchy: OWNER &gt; ADMIN &gt; REVIEWER &gt; CONTRIBUTOR &gt; VIEWER.
              </p>
            </div>
          </div>

          <button
            onClick={() => setAddMemberOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-1.5 cursor-pointer shadow-md"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Member</span>
          </button>
        </div>

        {loadingMembers ? (
          <div className="py-8 text-center">
            <Loader2 className="w-6 h-6 animate-spin text-copper-highlight mx-auto" />
          </div>
        ) : members.length === 0 ? (
          <div className="py-8 text-center text-xs text-secondary-text">
            No active members found.
          </div>
        ) : (
          <div className="rounded-xl border border-border-dark overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-secondary text-secondary-text border-b border-border-dark font-medium uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Joined Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-dark text-ivory/90">
                {members.map((m) => (
                  <tr key={m.id} className="hover:bg-white/5 transition-colors">
                    <td className="py-3 px-4 font-medium text-paper-white font-mono">{m.email}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-copper/20 text-copper-highlight border border-copper/30">
                        {m.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-secondary-text">
                      {new Date(m.joined_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {m.role !== 'owner' && (
                        <button
                          onClick={() => handleRemoveMember(m.id)}
                          className="p-1 text-secondary-text hover:text-red-400 cursor-pointer"
                          title="Remove member"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Account Password Change */}
      <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 shadow-xl">
        <div className="flex items-center space-x-3 border-b border-border-dark pb-4">
          <KeyRound className="w-5 h-5 text-copper-highlight" />
          <div>
            <h3 className="font-serif text-xl text-paper-white">Account Password</h3>
            <p className="text-xs text-secondary-text">
              Signed-in as: <strong className="text-paper-white">{user?.email}</strong>
            </p>
          </div>
        </div>

        {passSuccessMsg && (
          <div className="p-3.5 rounded-xl bg-chartreuse/10 border border-chartreuse/20 text-chartreuse text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{passSuccessMsg}</span>
          </div>
        )}

        {passErrorMsg && (
          <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{passErrorMsg}</span>
          </div>
        )}

        <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
          <div className="space-y-1">
            <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
              Current Password
            </label>
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
              New Password (min 8 chars)
            </label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
            />
          </div>

          <button
            type="submit"
            disabled={changingPass}
            className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider cursor-pointer shadow-md"
          >
            {changingPass ? 'Updating Password...' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* Add Member Modal */}
      {addMemberOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-charcoal border border-border-dark p-6 rounded-3xl space-y-4 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Add Workspace Member</h3>
              <button onClick={() => setAddMemberOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleAddMember} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Member Email
                </label>
                <input
                  type="email"
                  required
                  value={newMemberEmail}
                  onChange={(e) => setNewMemberEmail(e.target.value)}
                  placeholder="colleague@enterprise.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Assigned Workspace Role
                </label>
                <select
                  value={newMemberRole}
                  onChange={(e) => setNewMemberRole(e.target.value as any)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                >
                  <option value="admin">Admin (Manage policies & members)</option>
                  <option value="reviewer">Reviewer (Conduct reviews & approve decisions)</option>
                  <option value="contributor">Contributor (Submit content & revisions)</option>
                  <option value="viewer">Viewer (Read-only access)</option>
                </select>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setAddMemberOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addingMember}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {addingMember ? 'Adding...' : 'Add Member'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
