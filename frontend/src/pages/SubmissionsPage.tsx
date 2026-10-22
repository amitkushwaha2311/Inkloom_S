import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import {
  BrandPolicy,
  ContentRevision,
  ContentSubmission,
  ContentSubmissionDetail,
  VerificationRun,
} from '@/types/api'
import {
  FileText,
  Plus,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  Clock,
  History,
  X,
  ShieldCheck,
  ChevronRight,
  ArrowLeft,
} from 'lucide-react'

export const SubmissionsPage: React.FC = () => {
  const { activeWorkspace } = useAuth()
  const { id: routeSubmissionId } = useParams<{ id?: string }>()
  const navigate = useNavigate()

  const [submissions, setSubmissions] = useState<ContentSubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSub, setSelectedSub] = useState<ContentSubmissionDetail | null>(null)
  const [activeRevision, setActiveRevision] = useState<ContentRevision | null>(null)
  const [verificationRuns, setVerificationRuns] = useState<VerificationRun[]>([])
  const [policies, setPolicies] = useState<BrandPolicy[]>([])
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Modals & Forms
  const [createSubModalOpen, setCreateSubModalOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newContentType, setNewContentType] = useState('marketing_copy')
  const [newInitialContent, setNewInitialContent] = useState('')
  const [submittingNew, setSubmittingNew] = useState(false)

  // New Revision Form
  const [newRevBody, setNewRevBody] = useState('')
  const [newRevSummary, setNewRevSummary] = useState('')
  const [submittingRev, setSubmittingRev] = useState(false)

  // Trigger Verification
  const [selectedPolicyId, setSelectedPolicyId] = useState('')
  const [runningVerification, setRunningVerification] = useState(false)

  const loadSubmissions = async () => {
    if (!activeWorkspace) return
    setLoading(true)
    try {
      const res = await api.submissions.list(activeWorkspace.id)
      setSubmissions(res.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load submissions')
    } finally {
      setLoading(false)
    }
  }

  const loadPolicies = async () => {
    if (!activeWorkspace) return
    try {
      const res = await api.policies.list(activeWorkspace.id)
      const active = (res.items || []).filter((p) => p.status === 'active')
      setPolicies(active)
      if (active.length > 0 && !selectedPolicyId) {
        setSelectedPolicyId(active[0].id)
      }
    } catch {
      // Ignore
    }
  }

  const loadSubmissionDetail = async (subId: string) => {
    if (!activeWorkspace) return
    setLoadingDetail(true)
    try {
      const detail = await api.submissions.get(activeWorkspace.id, subId)
      setSelectedSub(detail)
      const latestRev = detail.revisions?.[detail.revisions.length - 1] || null
      setActiveRevision(latestRev)
      if (latestRev) {
        setNewRevBody(latestRev.content_body)
      }

      // Load runs
      const runsRes = await api.verification.listRuns(activeWorkspace.id, subId)
      setVerificationRuns(runsRes.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load submission details')
    } finally {
      setLoadingDetail(false)
    }
  }

  useEffect(() => {
    loadSubmissions()
    loadPolicies()
  }, [activeWorkspace])

  useEffect(() => {
    if (routeSubmissionId) {
      loadSubmissionDetail(routeSubmissionId)
    } else {
      setSelectedSub(null)
      setActiveRevision(null)
    }
  }, [routeSubmissionId, activeWorkspace])

  const handleCreateSubmission = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !newTitle.trim() || !newInitialContent.trim()) return
    setSubmittingNew(true)
    try {
      const res = await api.submissions.create(activeWorkspace.id, {
        title: newTitle.trim(),
        content_type: newContentType,
        initial_content: newInitialContent,
      })
      setCreateSubModalOpen(false)
      setNewTitle('')
      setNewInitialContent('')
      await loadSubmissions()
      navigate(`/app/submissions/${res.id}`)
    } catch (err: any) {
      alert(err.message || 'Failed to create submission')
    } finally {
      setSubmittingNew(false)
    }
  }

  const handleCreateRevision = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !selectedSub || !newRevBody.trim()) return
    setSubmittingRev(true)
    try {
      await api.submissions.addRevision(activeWorkspace.id, selectedSub.id, {
        content_body: newRevBody,
        change_summary: newRevSummary.trim() || undefined,
      })
      setNewRevSummary('')
      await loadSubmissionDetail(selectedSub.id)
    } catch (err: any) {
      alert(err.message || 'Failed to save revision')
    } finally {
      setSubmittingRev(false)
    }
  }

  const handleRunVerification = async () => {
    if (!activeWorkspace || !selectedSub || !activeRevision || !selectedPolicyId) return
    setRunningVerification(true)
    try {
      await api.verification.run(
        activeWorkspace.id,
        selectedSub.id,
        activeRevision.revision_number,
        { policy_id: selectedPolicyId }
      )
      await loadSubmissionDetail(selectedSub.id)
    } catch (err: any) {
      alert(err.message || 'Verification failed')
    } finally {
      setRunningVerification(false)
    }
  }

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Content Governance
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Submissions & Revision Lineage
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Authoritative revision trees, deterministic checks, and character coordinates.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {selectedSub && (
            <button
              onClick={() => navigate('/app/submissions')}
              className="px-3.5 py-2 rounded-xl bg-charcoal hover:bg-white/10 text-ivory text-xs font-semibold uppercase tracking-wider flex items-center space-x-1.5 transition-colors cursor-pointer border border-border-dark"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>All Submissions</span>
            </button>
          )}

          <button
            onClick={() => setCreateSubModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Submission</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
          <span className="text-xs uppercase tracking-wider text-secondary-text">
            Loading submissions...
          </span>
        </div>
      ) : selectedSub ? (
        /* Submission Detail View */
        <div className="space-y-8">
          {/* Detail Overview Bar */}
          <div className="p-6 rounded-3xl bg-charcoal border border-border-dark flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl">
            <div className="space-y-1.5">
              <div className="flex items-center space-x-2.5">
                <span className="text-[10px] uppercase font-semibold tracking-wider text-copper-highlight">
                  {selectedSub.content_type.replace('_', ' ')}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                    selectedSub.status === 'verified'
                      ? 'bg-chartreuse/20 text-chartreuse'
                      : 'bg-copper/20 text-copper-highlight'
                  }`}
                >
                  {selectedSub.status.replace('_', ' ')}
                </span>
              </div>
              <h2 className="text-2xl font-serif text-paper-white font-bold">{selectedSub.title}</h2>
              <div className="text-xs text-secondary-text flex items-center space-x-4">
                <span>Created: {new Date(selectedSub.created_at).toLocaleString()}</span>
                <span>Total Revisions: {selectedSub.revisions?.length || 0}</span>
              </div>
            </div>

            {/* Run Verification Action Box */}
            <div className="p-4 rounded-2xl bg-obsidian border border-border-dark flex items-center space-x-3 shrink-0">
              <div className="space-y-1">
                <div className="text-[10px] uppercase tracking-wider text-secondary-text font-medium">
                  Active Policy Engine
                </div>
                {policies.length === 0 ? (
                  <span className="text-xs text-red-400">No active policies found</span>
                ) : (
                  <select
                    value={selectedPolicyId}
                    onChange={(e) => setSelectedPolicyId(e.target.value)}
                    className="bg-charcoal text-ivory text-xs px-2.5 py-1.5 rounded-lg border border-border-dark focus:outline-none focus:ring-1 focus:ring-copper"
                  >
                    {policies.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (v{p.version})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <button
                onClick={handleRunVerification}
                disabled={runningVerification || policies.length === 0}
                className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
              >
                {runningVerification ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5" />
                )}
                <span>Verify Revision</span>
              </button>
            </div>
          </div>

          {/* Revision Switcher & Content */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left: Revision History & Content Editor */}
            <div className="lg:col-span-7 space-y-6">
              {/* Revision Tabs */}
              <div className="flex items-center space-x-2 overflow-x-auto pb-2">
                <span className="text-xs text-secondary-text font-medium uppercase mr-2 flex items-center">
                  <History className="w-3.5 h-3.5 mr-1" /> Revisions:
                </span>
                {selectedSub.revisions?.map((rev) => (
                  <button
                    key={rev.id}
                    onClick={() => {
                      setActiveRevision(rev)
                      setNewRevBody(rev.content_body)
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                      activeRevision?.id === rev.id
                        ? 'bg-copper text-white'
                        : 'bg-charcoal text-secondary-text hover:text-white'
                    }`}
                  >
                    Rev #{rev.revision_number}
                  </button>
                ))}
              </div>

              {/* Active Revision Content Box */}
              <div className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-border-dark pb-3 text-xs text-secondary-text">
                  <span className="font-semibold text-paper-white">
                    Revision #{activeRevision?.revision_number} Content
                  </span>
                  <span>
                    {activeRevision?.word_count || 0} words · {activeRevision?.character_count || 0}{' '}
                    chars
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-obsidian border border-border-dark font-mono text-xs text-ivory/90 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                  {activeRevision?.content_body}
                </div>

                {activeRevision?.change_summary && (
                  <div className="text-xs text-secondary-text bg-white/5 p-3 rounded-xl border border-white/5">
                    <span className="font-semibold text-copper-highlight">Change Summary:</span>{' '}
                    {activeRevision.change_summary}
                  </div>
                )}
              </div>

              {/* Create Next Revision Form */}
              <form
                onSubmit={handleCreateRevision}
                className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-4 shadow-xl text-left"
              >
                <div className="space-y-1">
                  <h3 className="font-serif text-lg text-paper-white">Add New Content Revision</h3>
                  <p className="text-xs text-secondary-text">
                    Create a new revision with edits or corrections while preserving historical
                    lineage.
                  </p>
                </div>

                <textarea
                  value={newRevBody}
                  onChange={(e) => setNewRevBody(e.target.value)}
                  rows={6}
                  placeholder="Paste or write revised copy..."
                  className="w-full p-4 rounded-xl bg-obsidian border border-border-dark text-white font-mono text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-copper"
                />

                <input
                  type="text"
                  value={newRevSummary}
                  onChange={(e) => setNewRevSummary(e.target.value)}
                  placeholder="Summary of changes (e.g. replaced unsubstantiated claim with 10-K metric)"
                  className="w-full px-4 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-xs focus:outline-none focus:ring-2 focus:ring-copper"
                />

                <button
                  type="submit"
                  disabled={submittingRev}
                  className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider flex items-center space-x-2 cursor-pointer"
                >
                  {submittingRev ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  <span>Commit Revision #{(selectedSub.revisions?.length || 0) + 1}</span>
                </button>
              </form>
            </div>

            {/* Right: Verification Findings & History */}
            <div className="lg:col-span-5 space-y-6">
              <div className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-border-dark pb-3">
                  <div className="flex items-center space-x-2">
                    <ShieldCheck className="w-5 h-5 text-copper-highlight" />
                    <h3 className="font-serif text-lg text-paper-white">Verification Engine Findings</h3>
                  </div>
                  <span className="text-[10px] uppercase font-semibold text-secondary-text">
                    {verificationRuns.length} runs executed
                  </span>
                </div>

                {verificationRuns.length === 0 ? (
                  <div className="py-12 text-center text-xs text-secondary-text space-y-2">
                    <AlertTriangle className="w-8 h-8 text-secondary-text mx-auto" />
                    <p>No verification runs executed on this submission yet.</p>
                    <p className="text-[11px] text-secondary-text/70">
                      Click "Verify Revision" above to evaluate against the active policy.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {verificationRuns.map((run) => (
                      <div
                        key={run.id}
                        className="p-4 rounded-2xl bg-obsidian border border-border-dark space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-paper-white font-mono">
                            Run for Rev #{run.revision_number}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                              run.passed
                                ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                                : 'bg-red-500/20 text-red-400 border border-red-500/30'
                            }`}
                          >
                            {run.passed ? 'Passed All Rules' : `${run.violations_count} Violations`}
                          </span>
                        </div>

                        {run.rule_findings && run.rule_findings.length > 0 ? (
                          <div className="space-y-2 pt-2 border-t border-border-dark">
                            {run.rule_findings.map((f, i) => (
                              <div
                                key={f.id || i}
                                className={`p-3 rounded-xl text-xs space-y-1 ${
                                  f.passed
                                    ? 'bg-chartreuse/5 border border-chartreuse/15 text-chartreuse'
                                    : 'bg-red-500/10 border border-red-500/20 text-red-300'
                                }`}
                              >
                                <div className="flex items-center justify-between font-semibold">
                                  <span>{f.message}</span>
                                  <span className="uppercase text-[9px] font-mono">
                                    {f.severity}
                                  </span>
                                </div>
                                {f.matched_text && (
                                  <div className="font-mono text-[11px] text-white/80 bg-black/40 px-2 py-1 rounded">
                                    Flagged: "{f.matched_text}" [idx {f.char_start}:{f.char_end}]
                                  </div>
                                )}
                                {f.recommendation && (
                                  <div className="text-[11px] text-secondary-text">
                                    Recommendation: {f.recommendation}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-chartreuse flex items-center space-x-1.5 pt-1">
                            <CheckCircle2 className="w-4 h-4" />
                            <span>100% Deterministic Compliance Verified.</span>
                          </div>
                        )}

                        <div className="text-[10px] text-secondary-text font-mono pt-1">
                          Executed: {new Date(run.created_at).toLocaleTimeString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Submissions List View */
        <div className="space-y-4">
          <div className="rounded-2xl bg-charcoal border border-border-dark overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-secondary text-secondary-text border-b border-border-dark font-medium uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4">Content Type</th>
                    <th className="py-3 px-4">Revisions</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Created Date</th>
                    <th className="py-3 px-4 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-dark text-ivory/90">
                  {submissions.map((sub) => (
                    <tr
                      key={sub.id}
                      onClick={() => navigate(`/app/submissions/${sub.id}`)}
                      className="hover:bg-white/5 transition-colors cursor-pointer"
                    >
                      <td className="py-3.5 px-4 font-semibold text-paper-white">{sub.title}</td>
                      <td className="py-3.5 px-4 uppercase text-[10px] text-secondary-text">
                        {sub.content_type.replace('_', ' ')}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[11px]">
                        Rev #{sub.current_revision_number}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
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
                      <td className="py-3.5 px-4 text-secondary-text">
                        {new Date(sub.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="text-copper-highlight font-medium flex items-center justify-end space-x-1">
                          <span>Inspect</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* New Submission Modal */}
      {createSubModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-charcoal border border-border-dark p-6 sm:p-8 rounded-3xl space-y-5 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Create Content Submission</h3>
              <button onClick={() => setCreateSubModalOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmission} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Submission Title
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Q4 Cloud Infrastructure Announcement"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Content Type
                </label>
                <select
                  value={newContentType}
                  onChange={(e) => setNewContentType(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                >
                  <option value="marketing_copy">Marketing Copy</option>
                  <option value="press_release">Press Release</option>
                  <option value="product_documentation">Product Documentation</option>
                  <option value="regulatory_filing">Regulatory Filing Excerpt</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Initial Content Body
                </label>
                <textarea
                  required
                  rows={6}
                  value={newInitialContent}
                  onChange={(e) => setNewInitialContent(e.target.value)}
                  placeholder="Paste or author the first revision text here..."
                  className="w-full p-3.5 rounded-xl bg-obsidian border border-border-dark text-white font-mono text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setCreateSubModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingNew}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {submittingNew ? 'Creating...' : 'Create Submission'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
