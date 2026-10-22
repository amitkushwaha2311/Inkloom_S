import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import {
  ContentClaim,
  ContentSubmission,
  EvidenceSource,
  EvidenceSourceType,
} from '@/types/api'
import {
  Database,
  Search,
  Plus,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  FileText,
  ExternalLink,
  X,
  Play,
  Check,
  Ban,
} from 'lucide-react'

export const EvidencePage: React.FC = () => {
  const { activeWorkspace } = useAuth()
  const [activeTab, setActiveTab] = useState<'sources' | 'claims'>('sources')

  // Sources State
  const [sources, setSources] = useState<EvidenceSource[]>([])
  const [loadingSources, setLoadingSources] = useState(true)

  // Claims State
  const [submissions, setSubmissions] = useState<ContentSubmission[]>([])
  const [selectedSubId, setSelectedSubId] = useState('')
  const [selectedRevNum, setSelectedRevNum] = useState(1)
  const [claims, setClaims] = useState<ContentClaim[]>([])
  const [loadingClaims, setLoadingClaims] = useState(false)
  const [discoveringClaims, setDiscoveringClaims] = useState(false)

  // Modals
  const [createSourceModalOpen, setCreateSourceModalOpen] = useState(false)
  const [sourceTitle, setSourceTitle] = useState('')
  const [sourceType, setSourceType] = useState<EvidenceSourceType>('regulatory_filing')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourcePublisher, setSourcePublisher] = useState('')
  const [sourceEffectiveDate, setSourceEffectiveDate] = useState(
    new Date().toISOString().split('T')[0]
  )
  const [sourceExcerpts, setSourceExcerpts] = useState('')
  const [submittingSource, setSubmittingSource] = useState(false)

  // Justification Modal for Reject/Revoke
  const [justificationModal, setJustificationModal] = useState<{
    open: boolean
    sourceId: string
    action: 'reject' | 'revoke'
    reason: string
  }>({ open: false, sourceId: '', action: 'reject', reason: '' })

  const loadSources = async () => {
    if (!activeWorkspace) return
    setLoadingSources(true)
    try {
      const res = await api.evidence.listSources(activeWorkspace.id)
      setSources(res.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load evidence sources')
    } finally {
      setLoadingSources(false)
    }
  }

  const loadSubmissions = async () => {
    if (!activeWorkspace) return
    try {
      const res = await api.submissions.list(activeWorkspace.id)
      setSubmissions(res.items || [])
      if (res.items && res.items.length > 0 && !selectedSubId) {
        setSelectedSubId(res.items[0].id)
        setSelectedRevNum(res.items[0].current_revision_number || 1)
      }
    } catch {
      // Ignore
    }
  }

  const loadClaims = async (subId: string, revNum: number) => {
    if (!activeWorkspace || !subId) return
    setLoadingClaims(true)
    try {
      const res = await api.evidence.listClaims(activeWorkspace.id, subId, revNum)
      setClaims(res.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load claims')
    } finally {
      setLoadingClaims(false)
    }
  }

  useEffect(() => {
    loadSources()
    loadSubmissions()
  }, [activeWorkspace])

  useEffect(() => {
    if (selectedSubId) {
      loadClaims(selectedSubId, selectedRevNum)
    }
  }, [selectedSubId, selectedRevNum, activeWorkspace])

  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !sourceTitle.trim() || !sourcePublisher.trim()) return
    setSubmittingSource(true)
    try {
      const excerpts = sourceExcerpts
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)

      await api.evidence.createSource(activeWorkspace.id, {
        title: sourceTitle.trim(),
        source_type: sourceType,
        source_url: sourceUrl.trim() || undefined,
        publisher_or_owner: sourcePublisher.trim(),
        effective_date: new Date(sourceEffectiveDate).toISOString(),
        trusted_excerpts: excerpts,
      })

      setCreateSourceModalOpen(false)
      setSourceTitle('')
      setSourceUrl('')
      setSourcePublisher('')
      setSourceExcerpts('')
      await loadSources()
    } catch (err: any) {
      alert(err.message || 'Failed to register source')
    } finally {
      setSubmittingSource(false)
    }
  }

  const handleApproveSource = async (sourceId: string) => {
    if (!activeWorkspace) return
    try {
      await api.evidence.approveSource(activeWorkspace.id, sourceId)
      await loadSources()
    } catch (err: any) {
      alert(err.message || 'Failed to approve source')
    }
  }

  const handleJustificationSubmit = async () => {
    if (!activeWorkspace || !justificationModal.sourceId || !justificationModal.reason.trim())
      return
    try {
      if (justificationModal.action === 'reject') {
        await api.evidence.rejectSource(
          activeWorkspace.id,
          justificationModal.sourceId,
          justificationModal.reason.trim()
        )
      } else {
        await api.evidence.revokeSource(
          activeWorkspace.id,
          justificationModal.sourceId,
          justificationModal.reason.trim()
        )
      }
      setJustificationModal({ open: false, sourceId: '', action: 'reject', reason: '' })
      await loadSources()
    } catch (err: any) {
      alert(err.message || 'Action failed')
    }
  }

  const handleDiscoverClaims = async () => {
    if (!activeWorkspace || !selectedSubId) return
    setDiscoveringClaims(true)
    try {
      await api.evidence.discoverClaims(activeWorkspace.id, selectedSubId, selectedRevNum)
      await loadClaims(selectedSubId, selectedRevNum)
    } catch (err: any) {
      alert(err.message || 'Claim discovery failed')
    } finally {
      setDiscoveringClaims(false)
    }
  }

  const handleAssessClaim = async (claimId: string) => {
    if (!activeWorkspace || !selectedSubId) return
    try {
      await api.evidence.assessClaim(
        activeWorkspace.id,
        selectedSubId,
        selectedRevNum,
        claimId
      )
      await loadClaims(selectedSubId, selectedRevNum)
    } catch (err: any) {
      alert(err.message || 'Claim assessment failed')
    }
  }

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-chartreuse">
            Ground Truth Intelligence
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Evidence Registry & Claim Provenance
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            SSRF-protected authoritative source records and conservative factual claim verification.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setCreateSourceModalOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Register Evidence Source</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-border-dark space-x-8 text-xs font-semibold uppercase tracking-wider">
        <button
          onClick={() => setActiveTab('sources')}
          className={`pb-3 cursor-pointer transition-colors border-b-2 flex items-center space-x-2 ${
            activeTab === 'sources'
              ? 'border-copper text-copper-highlight'
              : 'border-transparent text-secondary-text hover:text-white'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Evidence Sources Registry ({sources.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('claims')}
          className={`pb-3 cursor-pointer transition-colors border-b-2 flex items-center space-x-2 ${
            activeTab === 'claims'
              ? 'border-copper text-copper-highlight'
              : 'border-transparent text-secondary-text hover:text-white'
          }`}
        >
          <Search className="w-4 h-4" />
          <span>Factual Claims Discovery ({claims.length})</span>
        </button>
      </div>

      {/* Tab 1: Evidence Sources */}
      {activeTab === 'sources' && (
        <div className="space-y-6">
          {loadingSources ? (
            <div className="py-24 flex flex-col items-center justify-center space-y-4">
              <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
              <span className="text-xs uppercase tracking-wider text-secondary-text">
                Loading approved evidence sources...
              </span>
            </div>
          ) : sources.length === 0 ? (
            <div className="p-16 rounded-3xl bg-charcoal border border-border-dark text-center space-y-4">
              <Database className="w-10 h-10 text-secondary-text mx-auto" />
              <h3 className="text-base font-medium text-paper-white">No evidence sources registered</h3>
              <p className="text-xs text-secondary-text max-w-sm mx-auto">
                Register authoritative internal documents, SEC filings, or benchmark studies to
                prove claims made in content submissions.
              </p>
              <button
                onClick={() => setCreateSourceModalOpen(true)}
                className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider inline-flex items-center space-x-2 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Register First Source</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {sources.map((src) => (
                <div
                  key={src.id}
                  className="p-6 rounded-3xl bg-charcoal border border-border-dark flex flex-col justify-between space-y-4 text-left shadow-lg"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-copper-highlight">
                        {src.source_type.replace('_', ' ')}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                          src.approval_status === 'approved'
                            ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                            : src.approval_status === 'rejected'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : 'bg-copper/20 text-copper-highlight'
                        }`}
                      >
                        {src.approval_status.replace('_', ' ')}
                      </span>
                    </div>

                    <h3 className="font-serif text-lg font-bold text-paper-white line-clamp-2">
                      {src.title}
                    </h3>

                    <div className="text-xs text-secondary-text space-y-1">
                      <div>Publisher: <strong className="text-ivory/80">{src.publisher_or_owner}</strong></div>
                      <div>Effective: {new Date(src.effective_date).toLocaleDateString()}</div>
                      {src.source_url && (
                        <div className="truncate text-copper-highlight hover:underline flex items-center space-x-1">
                          <ExternalLink className="w-3 h-3 shrink-0" />
                          <span className="truncate">{src.source_url}</span>
                        </div>
                      )}
                    </div>

                    {src.trusted_excerpts && src.trusted_excerpts.length > 0 && (
                      <div className="p-3 rounded-xl bg-obsidian border border-border-dark text-[11px] font-mono text-ivory/80 line-clamp-3 italic">
                        "{src.trusted_excerpts[0]}"
                      </div>
                    )}
                  </div>

                  {/* Actions based on approval status */}
                  <div className="pt-3 border-t border-border-dark flex items-center justify-between text-xs">
                    {src.approval_status === 'draft' || src.approval_status === 'pending_approval' ? (
                      <div className="flex items-center space-x-2 w-full justify-end">
                        <button
                          onClick={() => handleApproveSource(src.id)}
                          className="px-3 py-1.5 rounded-lg bg-chartreuse/20 hover:bg-chartreuse/30 text-chartreuse font-semibold uppercase text-[10px] flex items-center space-x-1 cursor-pointer"
                        >
                          <Check className="w-3 h-3" />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() =>
                            setJustificationModal({
                              open: true,
                              sourceId: src.id,
                              action: 'reject',
                              reason: '',
                            })
                          }
                          className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 font-semibold uppercase text-[10px] cursor-pointer"
                        >
                          Reject
                        </button>
                      </div>
                    ) : src.approval_status === 'approved' ? (
                      <button
                        onClick={() =>
                          setJustificationModal({
                            open: true,
                            sourceId: src.id,
                            action: 'revoke',
                            reason: '',
                          })
                        }
                        className="text-[10px] text-secondary-text hover:text-red-400 font-semibold uppercase flex items-center space-x-1 cursor-pointer ml-auto"
                      >
                        <Ban className="w-3 h-3" />
                        <span>Revoke Source</span>
                      </button>
                    ) : (
                      <span className="text-[10px] text-secondary-text italic">
                        Inactive source record
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Content Claims & Discovery */}
      {activeTab === 'claims' && (
        <div className="space-y-6">
          {/* Submission and Revision Selector Bar */}
          <div className="p-4 rounded-2xl bg-charcoal border border-border-dark flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              <div className="space-y-1 text-left">
                <span className="text-[10px] uppercase font-semibold text-secondary-text tracking-wider">
                  Target Submission
                </span>
                <select
                  value={selectedSubId}
                  onChange={(e) => {
                    setSelectedSubId(e.target.value)
                    const s = submissions.find((sub) => sub.id === e.target.value)
                    if (s) setSelectedRevNum(s.current_revision_number || 1)
                  }}
                  className="bg-obsidian text-ivory text-xs px-3 py-2 rounded-xl border border-border-dark focus:outline-none focus:ring-1 focus:ring-copper"
                >
                  {submissions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title} (Rev #{s.current_revision_number})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={handleDiscoverClaims}
              disabled={discoveringClaims || !selectedSubId}
              className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
            >
              {discoveringClaims ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Search className="w-3.5 h-3.5" />
              )}
              <span>Run Automated Claim Discovery</span>
            </button>
          </div>

          {loadingClaims ? (
            <div className="py-24 flex flex-col items-center justify-center space-y-4">
              <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
              <span className="text-xs uppercase tracking-wider text-secondary-text">
                Extracting and indexing claims...
              </span>
            </div>
          ) : claims.length === 0 ? (
            <div className="p-16 rounded-3xl bg-charcoal border border-border-dark text-center space-y-4">
              <Search className="w-10 h-10 text-secondary-text mx-auto" />
              <h3 className="text-base font-medium text-paper-white">No claims indexed for this revision</h3>
              <p className="text-xs text-secondary-text max-w-sm mx-auto">
                Run the automated claim discovery engine on this submission to scan and evaluate
                assertions against approved evidence.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {claims.map((claim) => (
                <div
                  key={claim.id}
                  className="p-6 rounded-3xl bg-charcoal border border-border-dark space-y-4 text-left shadow-lg"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border-dark pb-3">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-copper-highlight">
                        {claim.claim_type.replace('_', ' ')}
                      </span>
                      <span className="text-secondary-text font-mono text-[10px]">
                        [chars {claim.char_start}:{claim.char_end}]
                      </span>
                    </div>

                    {/* Latest Assessment Badge */}
                    <div>
                      {claim.latest_assessment ? (
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            claim.latest_assessment.status === 'supported'
                              ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                              : claim.latest_assessment.status === 'contradicted'
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : 'bg-copper/20 text-copper-highlight border border-copper/30'
                          }`}
                        >
                          {claim.latest_assessment.status.replace('_', ' ')} (Score:{' '}
                          {claim.latest_assessment.confidence_score})
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-secondary-text/20 text-secondary-text">
                          Not Evaluated Yet
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Claim Text */}
                  <div className="space-y-1">
                    <div className="text-[10px] uppercase tracking-wider text-secondary-text font-medium">
                      Extracted Claim Text:
                    </div>
                    <div className="text-sm font-medium text-paper-white font-serif bg-obsidian p-3 rounded-xl border border-border-dark">
                      "{claim.claim_text}"
                    </div>
                  </div>

                  {/* Context excerpt */}
                  {claim.context_excerpt && (
                    <div className="text-xs text-secondary-text">
                      Context: <span className="italic">{claim.context_excerpt}</span>
                    </div>
                  )}

                  {/* Assessment Citation Reasoning */}
                  {claim.latest_assessment && (
                    <div className="p-3.5 rounded-xl bg-obsidian border border-border-dark text-xs space-y-1.5">
                      <div className="font-semibold text-paper-white flex items-center space-x-2">
                        <Shield className="w-3.5 h-3.5 text-copper-highlight" />
                        <span>Evidence Evaluation Reasoning</span>
                      </div>
                      <div className="text-secondary-text leading-relaxed">
                        {claim.latest_assessment.reasoning}
                      </div>
                      {claim.latest_assessment.supporting_excerpt && (
                        <div className="text-[11px] font-mono text-chartreuse bg-black/40 p-2 rounded">
                          Citing: "{claim.latest_assessment.supporting_excerpt}"
                        </div>
                      )}
                    </div>
                  )}

                  {/* Assess Trigger Action */}
                  <div className="flex items-center justify-end pt-2">
                    <button
                      onClick={() => handleAssessClaim(claim.id)}
                      className="px-4 py-2 rounded-xl bg-copper hover:bg-copper-highlight text-white font-semibold text-xs uppercase tracking-wider flex items-center space-x-1.5 cursor-pointer shadow-md"
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>Evaluate Against Evidence</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Register Source Modal */}
      {createSourceModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-charcoal border border-border-dark p-6 sm:p-8 rounded-3xl space-y-5 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Register Evidence Source</h3>
              <button onClick={() => setCreateSourceModalOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleCreateSource} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Document / Filing Title
                </label>
                <input
                  type="text"
                  required
                  value={sourceTitle}
                  onChange={(e) => setSourceTitle(e.target.value)}
                  placeholder="e.g. SEC Form 10-K FY2025 Filing"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                    Source Classification
                  </label>
                  <select
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value as any)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                  >
                    <option value="regulatory_filing">Regulatory Filing</option>
                    <option value="scientific_paper">Scientific Paper</option>
                    <option value="clinical_trial">Clinical Trial Report</option>
                    <option value="internal_policy">Internal Policy Document</option>
                    <option value="legal_contract">Legal Contract</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                    Publisher / Owner
                  </label>
                  <input
                    type="text"
                    required
                    value={sourcePublisher}
                    onChange={(e) => setSourcePublisher(e.target.value)}
                    placeholder="e.g. SEC Edgar / National Lab"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Source URL (SSRF Protected: http/https only)
                </label>
                <input
                  type="url"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://sec.gov/edgar/data/filing.pdf"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper font-mono text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Authoritative Trusted Excerpts (one per line)
                </label>
                <textarea
                  rows={3}
                  value={sourceExcerpts}
                  onChange={(e) => setSourceExcerpts(e.target.value)}
                  placeholder="Paste verbatim statements or facts to ground claims..."
                  className="w-full p-3.5 rounded-xl bg-obsidian border border-border-dark text-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setCreateSourceModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingSource}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {submittingSource ? 'Registering...' : 'Register Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Justification Modal */}
      {justificationModal.open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-charcoal border border-border-dark p-6 rounded-3xl space-y-4 text-left shadow-2xl">
            <h3 className="font-serif text-lg text-paper-white capitalize">
              {justificationModal.action} Evidence Source
            </h3>
            <p className="text-xs text-secondary-text">
              Provide an audit justification for this governance action.
            </p>

            <textarea
              required
              rows={3}
              value={justificationModal.reason}
              onChange={(e) =>
                setJustificationModal({ ...justificationModal, reason: e.target.value })
              }
              placeholder="e.g. Superseded by newer FY26 operational audit report."
              className="w-full p-3 rounded-xl bg-obsidian border border-border-dark text-white text-xs focus:outline-none focus:ring-2 focus:ring-copper"
            />

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() =>
                  setJustificationModal({ open: false, sourceId: '', action: 'reject', reason: '' })
                }
                className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleJustificationSubmit}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold uppercase tracking-wider"
              >
                Confirm {justificationModal.action}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
