import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import {
  BrandPolicy,
  ContentSubmission,
  CorrectionSuggestion,
  ReviewDecision,
  UnifiedReviewSummary,
} from '@/types/api'
import {
  Layers,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  Plus,
  Loader2,
  Sparkles,
  ArrowRight,
  UserCheck,
  X,
  FileCheck,
} from 'lucide-react'

export const UnifiedReviewPage: React.FC = () => {
  const { activeWorkspace, user } = useAuth()
  const [submissions, setSubmissions] = useState<ContentSubmission[]>([])
  const [policies, setPolicies] = useState<BrandPolicy[]>([])
  const [selectedSubId, setSelectedSubId] = useState('')
  const [selectedPolicyId, setSelectedPolicyId] = useState('')
  const [summary, setSummary] = useState<UnifiedReviewSummary | null>(null)
  const [corrections, setCorrections] = useState<CorrectionSuggestion[]>([])
  const [decisions, setDecisions] = useState<ReviewDecision[]>([])
  const [loading, setLoading] = useState(false)
  const [applyingCorrectionId, setApplyingCorrectionId] = useState<string | null>(null)

  // Decision Form
  const [decisionType, setDecisionType] = useState<'approved' | 'changes_requested' | 'rejected'>('approved')
  const [decisionComment, setDecisionComment] = useState('')
  const [submittingDecision, setSubmittingDecision] = useState(false)

  // Propose Correction Modal
  const [proposeModalOpen, setProposeModalOpen] = useState(false)
  const [origText, setOrigText] = useState('')
  const [replacementText, setReplacementText] = useState('')
  const [rationale, setRationale] = useState('')
  const [charStart, setCharStart] = useState(0)
  const [charEnd, setCharEnd] = useState(0)
  const [submittingCorrection, setSubmittingCorrection] = useState(false)

  const loadInitialData = async () => {
    if (!activeWorkspace) return
    try {
      const [subRes, polRes] = await Promise.all([
        api.submissions.list(activeWorkspace.id),
        api.policies.list(activeWorkspace.id),
      ])
      const subs = subRes.items || []
      const pols = (polRes.items || []).filter((p) => p.status === 'active')

      setSubmissions(subs)
      setPolicies(pols)

      if (subs.length > 0 && !selectedSubId) {
        setSelectedSubId(subs[0].id)
      }
      if (pols.length > 0 && !selectedPolicyId) {
        setSelectedPolicyId(pols[0].id)
      }
    } catch {
      // Ignore
    }
  }

  const loadUnifiedSummary = async (subId: string, polId: string) => {
    if (!activeWorkspace || !subId || !polId) return
    setLoading(true)
    try {
      const s = submissions.find((sub) => sub.id === subId)
      const revNum = s?.current_revision_number || 1
      const res = await api.reviews.getSummary(activeWorkspace.id, subId, revNum, polId)
      setSummary(res)

      // Load corrections and decisions
      const [corrRes, decRes] = await Promise.all([
        api.reviews.listCorrections(activeWorkspace.id, subId, revNum),
        api.reviews.listDecisions(activeWorkspace.id, subId, revNum),
      ])
      setCorrections(corrRes.items || [])
      setDecisions(decRes.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load unified review summary')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadInitialData()
  }, [activeWorkspace])

  useEffect(() => {
    if (selectedSubId && selectedPolicyId) {
      loadUnifiedSummary(selectedSubId, selectedPolicyId)
    }
  }, [selectedSubId, selectedPolicyId, activeWorkspace])

  const handleApplyCorrection = async (correctionId: string) => {
    if (!activeWorkspace || !selectedSubId) return
    setApplyingCorrectionId(correctionId)
    try {
      const s = submissions.find((sub) => sub.id === selectedSubId)
      const revNum = s?.current_revision_number || 1
      await api.reviews.applyCorrection(activeWorkspace.id, selectedSubId, revNum, correctionId)
      await loadInitialData()
      await loadUnifiedSummary(selectedSubId, selectedPolicyId)
    } catch (err: any) {
      alert(err.message || 'Failed to apply correction')
    } finally {
      setApplyingCorrectionId(null)
    }
  }

  const handleProposeCorrection = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !selectedSubId || !origText.trim() || !replacementText.trim()) return
    setSubmittingCorrection(true)
    try {
      const s = submissions.find((sub) => sub.id === selectedSubId)
      const revNum = s?.current_revision_number || 1
      await api.reviews.proposeCorrection(activeWorkspace.id, selectedSubId, revNum, {
        original_text: origText,
        proposed_replacement: replacementText,
        char_start: Number(charStart) || 0,
        char_end: Number(charEnd) || origText.length,
        rationale: rationale.trim(),
      })
      setProposeModalOpen(false)
      setOrigText('')
      setReplacementText('')
      setRationale('')
      await loadUnifiedSummary(selectedSubId, selectedPolicyId)
    } catch (err: any) {
      alert(err.message || 'Failed to propose correction')
    } finally {
      setSubmittingCorrection(false)
    }
  }

  const handleRecordDecision = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !selectedSubId) return
    setSubmittingDecision(true)
    try {
      const s = submissions.find((sub) => sub.id === selectedSubId)
      const revNum = s?.current_revision_number || 1
      await api.reviews.recordDecision(activeWorkspace.id, selectedSubId, revNum, {
        decision: decisionType,
        comment: decisionComment.trim() || undefined,
      })
      setDecisionComment('')
      await loadUnifiedSummary(selectedSubId, selectedPolicyId)
    } catch (err: any) {
      alert(err.message || 'Failed to record decision')
    } finally {
      setSubmittingDecision(false)
    }
  }

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Governance Certification
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Unified Review & Corrections
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Synthesizes deterministic verification, evidence claims, and human review decisions.
          </p>
        </div>

        <button
          onClick={() => setProposeModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Propose Correction</span>
        </button>
      </div>

      {/* Target Selector Bar */}
      <div className="p-4 rounded-2xl bg-charcoal border border-border-dark grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-1 text-left">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
            Content Submission
          </label>
          <select
            value={selectedSubId}
            onChange={(e) => setSelectedSubId(e.target.value)}
            className="w-full bg-obsidian text-ivory text-xs px-3 py-2.5 rounded-xl border border-border-dark focus:outline-none focus:ring-1 focus:ring-copper"
          >
            {submissions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} (Rev #{s.current_revision_number})
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1 text-left">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
            Active Brand Policy
          </label>
          <select
            value={selectedPolicyId}
            onChange={(e) => setSelectedPolicyId(e.target.value)}
            className="w-full bg-obsidian text-ivory text-xs px-3 py-2.5 rounded-xl border border-border-dark focus:outline-none focus:ring-1 focus:ring-copper"
          >
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (v{p.version})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
          <span className="text-xs uppercase tracking-wider text-secondary-text">
            Synthesizing review engines...
          </span>
        </div>
      ) : summary ? (
        <div className="space-y-8">
          {/* Overall Determination Banner */}
          <div
            className={`p-6 rounded-3xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-left shadow-xl ${
              summary.overall_status === 'pass'
                ? 'bg-chartreuse/10 border-chartreuse/30 text-chartreuse'
                : summary.overall_status === 'action_required'
                ? 'bg-red-500/10 border-red-500/30 text-red-300'
                : 'bg-copper/10 border-copper/30 text-copper-highlight'
            }`}
          >
            <div className="flex items-center space-x-3.5">
              {summary.overall_status === 'pass' ? (
                <CheckCircle2 className="w-8 h-8 text-chartreuse shrink-0" />
              ) : summary.overall_status === 'action_required' ? (
                <XCircle className="w-8 h-8 text-red-400 shrink-0" />
              ) : (
                <AlertTriangle className="w-8 h-8 text-copper-highlight shrink-0" />
              )}
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-widest block">
                  Overall Compliance Determination
                </span>
                <h2 className="text-2xl font-serif font-bold capitalize">
                  {summary.overall_status.replace('_', ' ')}
                </h2>
              </div>
            </div>

            <div className="text-xs font-mono">
              Submission Rev #{summary.revision_number} · Policy v{summary.policy_version}
            </div>
          </div>

          {/* Tri-Engine Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
            {/* Engine 1: Deterministic */}
            <div className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
                Deterministic Engine
              </span>
              <div className="text-xl font-serif text-paper-white font-bold flex items-center space-x-2">
                {summary.deterministic_run?.passed ? (
                  <span className="text-chartreuse">Passed (0 Violations)</span>
                ) : summary.deterministic_run ? (
                  <span className="text-red-400">
                    {summary.deterministic_run.violations_count} Violations
                  </span>
                ) : (
                  <span className="text-secondary-text">Not Run Yet</span>
                )}
              </div>
              <p className="text-xs text-secondary-text">
                Evaluated against regex patterns and keyword rules.
              </p>
            </div>

            {/* Engine 2: Evidence Claims */}
            <div className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
                Factual Evidence Claims
              </span>
              <div className="text-xl font-serif text-paper-white font-bold">
                <span className="text-chartreuse">{summary.claims_supported_count} Supported</span>{' '}
                <span className="text-secondary-text">/ {summary.claims_assessed_count} Total</span>
              </div>
              <p className="text-xs text-secondary-text">
                {summary.claims_flagged_count} claims flagged for human or proof review.
              </p>
            </div>

            {/* Engine 3: Semantic Engine */}
            <div className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-secondary-text">
                Semantic Brand Voice
              </span>
              <div className="text-xl font-serif text-paper-white font-bold capitalize">
                {summary.semantic_run?.overall_outcome || 'Pending Review'}
              </div>
              <p className="text-xs text-secondary-text">
                Tone modesty, superlative scrutiny, and injection protection.
              </p>
            </div>
          </div>

          {/* Correction Suggestions Section */}
          <div className="space-y-4 text-left">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <div>
                <h3 className="font-serif text-xl text-paper-white">Correction Suggestions</h3>
                <p className="text-xs text-secondary-text">
                  Applying a correction creates a new revision without mutating historical drafts.
                </p>
              </div>

              <button
                onClick={() => setProposeModalOpen(true)}
                className="px-3.5 py-1.5 rounded-lg bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-1 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Propose</span>
              </button>
            </div>

            {corrections.length === 0 ? (
              <div className="p-8 rounded-2xl bg-charcoal border border-border-dark text-center text-xs text-secondary-text">
                No correction suggestions currently proposed for this revision.
              </div>
            ) : (
              <div className="space-y-3">
                {corrections.map((corr) => (
                  <div
                    key={corr.id}
                    className="p-5 rounded-2xl bg-charcoal border border-border-dark space-y-3 shadow-md"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-secondary-text text-[11px]">
                        Target offset: [{corr.char_start}:{corr.char_end}]
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                          corr.status === 'accepted'
                            ? 'bg-chartreuse/20 text-chartreuse'
                            : corr.status === 'proposed'
                            ? 'bg-copper/20 text-copper-highlight'
                            : 'bg-secondary-text/20 text-secondary-text'
                        }`}
                      >
                        {corr.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                      <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 line-through">
                        "{corr.original_text}"
                      </div>
                      <div className="p-3 rounded-xl bg-chartreuse/10 border border-chartreuse/20 text-chartreuse">
                        "{corr.proposed_replacement}"
                      </div>
                    </div>

                    <div className="text-xs text-secondary-text">
                      <strong>Rationale:</strong> {corr.rationale}
                    </div>

                    {corr.status === 'proposed' && (
                      <div className="flex items-center justify-end pt-2">
                        <button
                          onClick={() => handleApplyCorrection(corr.id)}
                          disabled={applyingCorrectionId === corr.id}
                          className="px-4 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider flex items-center space-x-2 cursor-pointer shadow-md"
                        >
                          {applyingCorrectionId === corr.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          )}
                          <span>Apply & Generate New Revision</span>
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Formal Governance Decision Form (Separation of Duties) */}
          <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 text-left shadow-xl">
            <div className="flex items-center space-x-3 border-b border-border-dark pb-4">
              <UserCheck className="w-6 h-6 text-copper-highlight" />
              <div>
                <h3 className="font-serif text-xl text-paper-white">
                  Formal Reviewer Determination
                </h3>
                <p className="text-xs text-secondary-text">
                  Enforces separation of duties. Submissions cannot be approved by their original author.
                </p>
              </div>
            </div>

            {summary.approval_block_reason && (
              <div className="p-4 rounded-xl bg-copper/10 border border-copper/30 text-copper-highlight text-xs flex items-start space-x-2.5">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <strong>Separation of Duties Notice:</strong> {summary.approval_block_reason}
                </span>
              </div>
            )}

            <form onSubmit={handleRecordDecision} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {(['approved', 'changes_requested', 'rejected'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setDecisionType(t)}
                    className={`py-3 px-4 rounded-xl text-xs font-semibold uppercase tracking-wider border cursor-pointer transition-all ${
                      decisionType === t
                        ? t === 'approved'
                          ? 'bg-chartreuse text-obsidian border-chartreuse shadow-md font-bold'
                          : t === 'rejected'
                          ? 'bg-red-500 text-white border-red-500 shadow-md font-bold'
                          : 'bg-copper text-white border-copper shadow-md font-bold'
                        : 'bg-obsidian border-border-dark text-secondary-text hover:text-white'
                    }`}
                  >
                    {t.replace('_', ' ')}
                  </button>
                ))}
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Governance Rationale & Audit Comment
                </label>
                <textarea
                  rows={3}
                  value={decisionComment}
                  onChange={(e) => setDecisionComment(e.target.value)}
                  placeholder="Mandatory notes explaining reasoning for approval or requested modifications..."
                  className="w-full p-3.5 rounded-xl bg-obsidian border border-border-dark text-white text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end pt-2">
                <button
                  type="submit"
                  disabled={submittingDecision || (!summary.can_approve && decisionType === 'approved')}
                  className="px-6 py-3 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider flex items-center space-x-2 cursor-pointer shadow-lg"
                >
                  {submittingDecision ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <FileCheck className="w-4 h-4" />
                  )}
                  <span>Commit Governance Determination</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        <div className="p-16 rounded-3xl bg-charcoal border border-border-dark text-center text-xs text-secondary-text">
          Select a submission and active policy to compute the unified review synthesis.
        </div>
      )}

      {/* Propose Correction Modal */}
      {proposeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-charcoal border border-border-dark p-6 sm:p-8 rounded-3xl space-y-5 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Propose Structured Correction</h3>
              <button onClick={() => setProposeModalOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleProposeCorrection} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Original Flagged Text
                </label>
                <textarea
                  required
                  rows={2}
                  value={origText}
                  onChange={(e) => setOrigText(e.target.value)}
                  placeholder="Exact string to be replaced..."
                  className="w-full p-3 rounded-xl bg-obsidian border border-border-dark text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Proposed Replacement Text
                </label>
                <textarea
                  required
                  rows={2}
                  value={replacementText}
                  onChange={(e) => setReplacementText(e.target.value)}
                  placeholder="Approved evidence-backed wording..."
                  className="w-full p-3 rounded-xl bg-obsidian border border-border-dark text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Correction Rationale
                </label>
                <input
                  type="text"
                  required
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="e.g. Aligns with SEC Form 10-K reported performance metrics."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-xs focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setProposeModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingCorrection}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {submittingCorrection ? 'Submitting...' : 'Submit Suggestion'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
