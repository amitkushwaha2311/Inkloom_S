import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import { ContentSubmission, GovernanceAnalytics, BrandPolicy } from '@/types/api'
import {
  FileCheck,
  FileText,
  ShieldCheck,
  ArrowRight,
  Plus,
  Loader2,
  Layers,
  Building2,
} from 'lucide-react'

export const DashboardOverviewPage: React.FC = () => {
  const { activeWorkspace, createWorkspace } = useAuth()
  const [loading, setLoading] = useState(true)
  const [policies, setPolicies] = useState<BrandPolicy[]>([])
  const [submissions, setSubmissions] = useState<ContentSubmission[]>([])
  const [analytics, setAnalytics] = useState<GovernanceAnalytics | null>(null)

  // Create-workspace inline form state
  const [wsName, setWsName] = useState('')
  const [wsDesc, setWsDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    if (!activeWorkspace) return
    let isMounted = true

    const loadData = async () => {
      setLoading(true)
      try {
        const [polRes, subRes, anaRes] = await Promise.allSettled([
          api.policies.list(activeWorkspace.id),
          api.submissions.list(activeWorkspace.id),
          api.audit.getAnalytics(activeWorkspace.id),
        ])

        if (isMounted) {
          if (polRes.status === 'fulfilled') setPolicies(polRes.value.items || [])
          if (subRes.status === 'fulfilled') setSubmissions(subRes.value.items || [])
          if (anaRes.status === 'fulfilled') setAnalytics(anaRes.value)
        }
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    loadData()
    return () => {
      isMounted = false
    }
  }, [activeWorkspace])

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!wsName.trim()) return
    setCreateError(null)
    setCreating(true)
    try {
      await createWorkspace({ name: wsName.trim(), description: wsDesc.trim() || undefined })
      setWsName('')
      setWsDesc('')
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create workspace')
    } finally {
      setCreating(false)
    }
  }

  // No workspace — show actionable create form, not just a text message.
  if (!activeWorkspace) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-full max-w-md space-y-6 animate-fade-up">
          <div className="text-center space-y-2">
            <div className="w-14 h-14 rounded-2xl bg-copper/15 border border-copper/30 flex items-center justify-center mx-auto">
              <Building2 className="w-7 h-7 text-copper-highlight" />
            </div>
            <h1 className="font-serif text-2xl text-paper-white">Create your first workspace</h1>
            <p className="text-xs text-secondary-text max-w-xs mx-auto">
              Workspaces isolate your brand policies, content submissions, and audit logs.
              Create one to get started.
            </p>
          </div>

          <form
            onSubmit={handleCreateWorkspace}
            className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-4"
          >
            <div className="space-y-1">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-secondary-text">
                Workspace Name <span className="text-copper-highlight">*</span>
              </label>
              <input
                id="ws-name-input"
                type="text"
                required
                value={wsName}
                onChange={(e) => setWsName(e.target.value)}
                placeholder="e.g. Acme Health Brand Governance"
                className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-secondary-text">
                Description <span className="text-secondary-text/60">(optional)</span>
              </label>
              <textarea
                id="ws-desc-input"
                value={wsDesc}
                onChange={(e) => setWsDesc(e.target.value)}
                placeholder="Primary workspace for consumer product packaging guidelines."
                rows={2}
                className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white placeholder-secondary-text text-sm focus:outline-none focus:ring-2 focus:ring-copper resize-none"
              />
            </div>

            {createError && (
              <p className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg">
                {createError}
              </p>
            )}

            <button
              id="create-workspace-submit"
              type="submit"
              disabled={creating || !wsName.trim()}
              className="w-full py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider flex items-center justify-center space-x-2 transition-colors"
            >
              {creating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              <span>{creating ? 'Creating…' : 'Create Workspace'}</span>
            </button>
          </form>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
        <span className="text-xs uppercase tracking-wider text-secondary-text">
          Loading workspace intelligence...
        </span>
      </div>
    )
  }

  const activePoliciesCount = policies.filter((p) => p.status === 'active').length

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Top Header & Context Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Workspace Console
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            {activeWorkspace.name}
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Governance Overview · Active Tenant: {activeWorkspace.slug}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            to="/app/submissions"
            className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Submission</span>
          </Link>
          <Link
            to="/app/policies"
            className="px-4 py-2.5 rounded-xl bg-charcoal hover:bg-white/10 border border-border-dark text-ivory text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 transition-colors"
          >
            <FileCheck className="w-3.5 h-3.5" />
            <span>Manage Policies</span>
          </Link>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
              Active Policies
            </span>
            <FileCheck className="w-4 h-4 text-copper-highlight" />
          </div>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {activePoliciesCount}
          </div>
          <div className="text-[11px] text-secondary-text">
            {policies.length} total registered policy definitions
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
              Content Submissions
            </span>
            <FileText className="w-4 h-4 text-chartreuse" />
          </div>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.total_submissions ?? submissions.length}
          </div>
          <div className="text-[11px] text-secondary-text">
            Across draft, review, and published states
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
              Compliance Pass Rate
            </span>
            <ShieldCheck className="w-4 h-4 text-chartreuse" />
          </div>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.policy_pass_rate !== undefined
              ? `${Math.round(analytics.policy_pass_rate * 100)}%`
              : 'N/A'}
          </div>
          <div className="text-[11px] text-secondary-text">
            Deterministic rule pass rate
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
              Total Verifications
            </span>
            <Layers className="w-4 h-4 text-copper" />
          </div>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.total_verifications ?? 0}
          </div>
          <div className="text-[11px] text-secondary-text">
            Automated verification run executions
          </div>
        </div>
      </div>

      {/* Recent Submissions Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-serif text-paper-white">Recent Content Submissions</h2>
            <p className="text-xs text-secondary-text">
              Content revisions awaiting verification or governance approval.
            </p>
          </div>
          <Link
            to="/app/submissions"
            className="text-xs text-copper-highlight hover:underline flex items-center space-x-1"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {submissions.length === 0 ? (
          <div className="p-12 rounded-2xl bg-charcoal border border-border-dark text-center space-y-3">
            <FileText className="w-8 h-8 text-secondary-text mx-auto" />
            <div className="text-sm font-medium text-paper-white">No content submissions yet</div>
            <p className="text-xs text-secondary-text max-w-sm mx-auto">
              Create your first content submission to run deterministic policy verification and
              claim assessments.
            </p>
            <Link
              to="/app/submissions"
              className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider mt-2"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Submission</span>
            </Link>
          </div>
        ) : (
          <div className="rounded-2xl bg-charcoal border border-border-dark overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-secondary text-secondary-text border-b border-border-dark font-medium uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4">Content Type</th>
                    <th className="py-3 px-4">Revision</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Updated</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-dark text-ivory/90">
                  {submissions.slice(0, 5).map((sub) => (
                    <tr key={sub.id} className="hover:bg-white/5 transition-colors">
                      <td className="py-3 px-4 font-medium text-paper-white">{sub.title}</td>
                      <td className="py-3 px-4 uppercase text-[10px] text-secondary-text">
                        {sub.content_type}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px]">
                        Rev #{sub.current_revision_number}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            sub.status === 'verified'
                              ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                              : sub.status === 'in_review'
                              ? 'bg-copper/20 text-copper-highlight border border-copper/30'
                              : 'bg-white/10 text-ivory/80'
                          }`}
                        >
                          {sub.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-secondary-text">
                        {new Date(sub.updated_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/app/submissions/${sub.id}`}
                          className="text-copper-highlight hover:text-white font-medium"
                        >
                          Review &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
