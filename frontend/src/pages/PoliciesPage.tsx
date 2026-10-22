import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import { BrandPolicy, BrandPolicyDetail, PolicyCategory, PolicyGuideline } from '@/types/api'
import {
  FileCheck,
  Plus,
  Loader2,
  CheckCircle2,
  AlertOctagon,
  Trash2,
  X,
  Shield,
  Layers,
  ChevronRight,
} from 'lucide-react'

export const PoliciesPage: React.FC = () => {
  const { activeWorkspace } = useAuth()
  const [policies, setPolicies] = useState<BrandPolicy[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPolicy, setSelectedPolicy] = useState<BrandPolicyDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Modals
  const [createPolicyOpen, setCreatePolicyOpen] = useState(false)
  const [newPolicyName, setNewPolicyName] = useState('')
  const [newPolicyDesc, setNewPolicyDesc] = useState('')
  const [newPolicyCategory, setNewPolicyCategory] = useState<PolicyCategory>('regulatory')
  const [submittingPolicy, setSubmittingPolicy] = useState(false)

  // Guideline Modal
  const [addGuidelineOpen, setAddGuidelineOpen] = useState(false)
  const [guidelineName, setGuidelineName] = useState('')
  const [guidelineSeverity, setGuidelineSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('high')
  const [guidelineRuleType, setGuidelineRuleType] = useState('regex_match')
  const [guidelinePattern, setGuidelinePattern] = useState('')
  const [submittingGuideline, setSubmittingGuideline] = useState(false)

  const loadPolicies = async () => {
    if (!activeWorkspace) return
    setLoading(true)
    try {
      const res = await api.policies.list(activeWorkspace.id)
      setPolicies(res.items || [])
    } catch (err: any) {
      alert(err.message || 'Failed to load policies')
    } finally {
      setLoading(false)
    }
  }

  const loadPolicyDetail = async (policyId: string) => {
    if (!activeWorkspace) return
    setLoadingDetail(true)
    try {
      const detail = await api.policies.get(activeWorkspace.id, policyId)
      setSelectedPolicy(detail)
    } catch (err: any) {
      alert(err.message || 'Failed to load policy details')
    } finally {
      setLoadingDetail(false)
    }
  }

  useEffect(() => {
    loadPolicies()
  }, [activeWorkspace])

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !newPolicyName.trim()) return
    setSubmittingPolicy(true)
    try {
      await api.policies.create(activeWorkspace.id, {
        name: newPolicyName.trim(),
        description: newPolicyDesc.trim() || undefined,
        category: newPolicyCategory,
      })
      setCreatePolicyOpen(false)
      setNewPolicyName('')
      setNewPolicyDesc('')
      await loadPolicies()
    } catch (err: any) {
      alert(err.message || 'Failed to create policy')
    } finally {
      setSubmittingPolicy(false)
    }
  }

  const handleActivate = async (policyId: string) => {
    if (!activeWorkspace) return
    try {
      await api.policies.activate(activeWorkspace.id, policyId)
      await loadPolicies()
      if (selectedPolicy?.id === policyId) {
        await loadPolicyDetail(policyId)
      }
    } catch (err: any) {
      alert(err.message || 'Failed to activate policy')
    }
  }

  const handleDeprecate = async (policyId: string) => {
    if (!activeWorkspace) return
    if (!confirm('Are you sure you want to deprecate this policy? Deprecated policies cannot be used for new verifications.')) return
    try {
      await api.policies.deprecate(activeWorkspace.id, policyId)
      await loadPolicies()
      if (selectedPolicy?.id === policyId) {
        await loadPolicyDetail(policyId)
      }
    } catch (err: any) {
      alert(err.message || 'Failed to deprecate policy')
    }
  }

  const handleAddGuideline = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeWorkspace || !selectedPolicy || !guidelineName.trim()) return
    setSubmittingGuideline(true)
    try {
      const patterns = guidelinePattern
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean)

      await api.policies.addGuideline(activeWorkspace.id, selectedPolicy.id, {
        name: guidelineName.trim(),
        category: selectedPolicy.category,
        severity: guidelineSeverity,
        rule_type: guidelineRuleType,
        rule_config: { patterns: patterns.length > 0 ? patterns : [guidelinePattern.trim()] },
      })

      setAddGuidelineOpen(false)
      setGuidelineName('')
      setGuidelinePattern('')
      await loadPolicyDetail(selectedPolicy.id)
    } catch (err: any) {
      alert(err.message || 'Failed to add guideline')
    } finally {
      setSubmittingGuideline(false)
    }
  }

  const handleDeleteGuideline = async (guidelineId: string) => {
    if (!activeWorkspace || !selectedPolicy) return
    if (!confirm('Are you sure you want to delete this guideline rule?')) return
    try {
      await api.policies.deleteGuideline(activeWorkspace.id, selectedPolicy.id, guidelineId)
      await loadPolicyDetail(selectedPolicy.id)
    } catch (err: any) {
      alert(err.message || 'Failed to delete guideline')
    }
  }

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Governance Specifications
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Brand & Regulatory Policies
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Versioned, immutable policy contracts with deterministic guideline rules.
          </p>
        </div>

        <button
          onClick={() => setCreatePolicyOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-2 shadow-md cursor-pointer transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Policy</span>
        </button>
      </div>

      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
          <span className="text-xs uppercase tracking-wider text-secondary-text">
            Fetching policies...
          </span>
        </div>
      ) : policies.length === 0 ? (
        <div className="p-16 rounded-2xl bg-charcoal border border-border-dark text-center space-y-4">
          <FileCheck className="w-10 h-10 text-secondary-text mx-auto" />
          <h3 className="text-base font-medium text-paper-white">No policies defined yet</h3>
          <p className="text-xs text-secondary-text max-w-sm mx-auto">
            Create an active policy with guideline rules to run deterministic compliance checks on
            content submissions.
          </p>
          <button
            onClick={() => setCreatePolicyOpen(true)}
            className="px-5 py-2.5 rounded-xl bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider inline-flex items-center space-x-2 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create First Policy</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Policy List */}
          <div className="lg:col-span-5 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-secondary-text px-1">
              Policies ({policies.length})
            </div>
            {policies.map((p) => {
              const isSelected = selectedPolicy?.id === p.id
              return (
                <div
                  key={p.id}
                  onClick={() => loadPolicyDetail(p.id)}
                  className={`p-4 rounded-2xl border text-left cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-charcoal border-copper/50 shadow-lg ring-1 ring-copper/20'
                      : 'bg-charcoal/60 border-border-dark hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center justify-between pb-2">
                    <span className="text-[10px] uppercase font-semibold tracking-wider text-copper-highlight">
                      {p.category.replace('_', ' ')}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                        p.status === 'active'
                          ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                          : p.status === 'draft'
                          ? 'bg-copper/20 text-copper-highlight border border-copper/30'
                          : 'bg-secondary-text/20 text-secondary-text border border-secondary-text/30'
                      }`}
                    >
                      {p.status} (v{p.version})
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-paper-white">{p.name}</h3>
                  {p.description && (
                    <p className="text-xs text-secondary-text line-clamp-2 mt-1">
                      {p.description}
                    </p>
                  )}

                  <div className="pt-3 mt-3 border-t border-border-dark flex items-center justify-between text-[11px] text-secondary-text">
                    <span>Updated {new Date(p.updated_at).toLocaleDateString()}</span>
                    <ChevronRight className="w-3.5 h-3.5 text-copper-highlight" />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Policy Detail Panel */}
          <div className="lg:col-span-7">
            {selectedPolicy ? (
              <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 text-left shadow-xl">
                {/* Detail Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-copper-highlight">
                        {selectedPolicy.category.replace('_', ' ')} · v{selectedPolicy.version}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[9px] font-semibold uppercase tracking-wider ${
                          selectedPolicy.status === 'active'
                            ? 'bg-chartreuse/20 text-chartreuse'
                            : selectedPolicy.status === 'draft'
                            ? 'bg-copper/20 text-copper-highlight'
                            : 'bg-secondary-text/20 text-secondary-text'
                        }`}
                      >
                        {selectedPolicy.status}
                      </span>
                    </div>
                    <h2 className="text-xl font-serif text-paper-white mt-1">
                      {selectedPolicy.name}
                    </h2>
                  </div>

                  <div className="flex items-center space-x-2">
                    {selectedPolicy.status === 'draft' && (
                      <button
                        onClick={() => handleActivate(selectedPolicy.id)}
                        className="px-3.5 py-1.5 rounded-lg bg-chartreuse/20 hover:bg-chartreuse/30 text-chartreuse text-xs font-semibold uppercase tracking-wider border border-chartreuse/40 cursor-pointer"
                      >
                        Activate Policy
                      </button>
                    )}
                    {selectedPolicy.status === 'active' && (
                      <button
                        onClick={() => handleDeprecate(selectedPolicy.id)}
                        className="px-3.5 py-1.5 rounded-lg bg-secondary-text/20 hover:bg-secondary-text/30 text-secondary-text text-xs font-semibold uppercase tracking-wider cursor-pointer"
                      >
                        Deprecate
                      </button>
                    )}
                  </div>
                </div>

                {selectedPolicy.description && (
                  <p className="text-xs text-ivory/80 leading-relaxed">
                    {selectedPolicy.description}
                  </p>
                )}

                {/* Guidelines Section */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-paper-white">
                        Guideline Rules ({selectedPolicy.guidelines?.length || 0})
                      </h4>
                      <p className="text-[11px] text-secondary-text">
                        Deterministic matching rules evaluated against content revisions.
                      </p>
                    </div>

                    <button
                      onClick={() => setAddGuidelineOpen(true)}
                      className="px-3 py-1.5 rounded-lg bg-copper hover:bg-copper-highlight text-white text-xs font-semibold uppercase tracking-wider flex items-center space-x-1 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add Rule</span>
                    </button>
                  </div>

                  {!selectedPolicy.guidelines || selectedPolicy.guidelines.length === 0 ? (
                    <div className="p-8 rounded-xl bg-obsidian/60 border border-border-dark text-center text-xs text-secondary-text">
                      No guideline rules registered for this policy yet. Add a regex or keyword rule.
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {selectedPolicy.guidelines.map((g) => (
                        <div
                          key={g.id}
                          className="p-3.5 rounded-xl bg-obsidian/80 border border-border-dark flex items-start justify-between gap-4"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center space-x-2">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                                  g.severity === 'critical'
                                    ? 'bg-red-500/20 text-red-400'
                                    : g.severity === 'high'
                                    ? 'bg-copper/20 text-copper-highlight'
                                    : 'bg-chartreuse/20 text-chartreuse'
                                }`}
                              >
                                {g.severity}
                              </span>
                              <span className="font-semibold text-xs text-paper-white">
                                {g.name}
                              </span>
                              <span className="text-[10px] font-mono text-secondary-text">
                                ({g.rule_type})
                              </span>
                            </div>

                            {g.rule_config?.patterns && (
                              <div className="text-[11px] text-secondary-text font-mono flex items-center space-x-1.5">
                                <span className="text-secondary-text/60">Patterns:</span>
                                <span className="text-copper-highlight">
                                  {JSON.stringify(g.rule_config.patterns)}
                                </span>
                              </div>
                            )}
                          </div>

                          <button
                            onClick={() => handleDeleteGuideline(g.id)}
                            className="p-1.5 text-secondary-text hover:text-red-400 rounded-lg hover:bg-white/5 cursor-pointer"
                            title="Delete guideline"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-16 rounded-3xl bg-charcoal/40 border border-border-dark text-center text-secondary-text text-xs">
                Select a policy from the list to view guidelines and configuration.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Policy Modal */}
      {createPolicyOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-charcoal border border-border-dark p-6 rounded-3xl space-y-5 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Create Brand Policy</h3>
              <button onClick={() => setCreatePolicyOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleCreatePolicy} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Policy Name
                </label>
                <input
                  type="text"
                  required
                  value={newPolicyName}
                  onChange={(e) => setNewPolicyName(e.target.value)}
                  placeholder="e.g. Q3 Commercial Advertising Guidelines"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Category
                </label>
                <select
                  value={newPolicyCategory}
                  onChange={(e) => setNewPolicyCategory(e.target.value as PolicyCategory)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                >
                  <option value="regulatory">Regulatory</option>
                  <option value="brand_voice">Brand Voice</option>
                  <option value="claims_evidence">Claims & Evidence</option>
                  <option value="content_safety">Content Safety</option>
                  <option value="editorial">Editorial</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Description (Optional)
                </label>
                <textarea
                  value={newPolicyDesc}
                  onChange={(e) => setNewPolicyDesc(e.target.value)}
                  placeholder="Mandatory rules for all public consumer copy."
                  rows={2}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setCreatePolicyOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingPolicy}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {submittingPolicy ? 'Creating...' : 'Create Policy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Guideline Modal */}
      {addGuidelineOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-charcoal border border-border-dark p-6 rounded-3xl space-y-5 text-left shadow-2xl">
            <div className="flex items-center justify-between border-b border-border-dark pb-3">
              <h3 className="font-serif text-xl text-paper-white">Add Guideline Rule</h3>
              <button onClick={() => setAddGuidelineOpen(false)}>
                <X className="w-5 h-5 text-secondary-text hover:text-white" />
              </button>
            </div>

            <form onSubmit={handleAddGuideline} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Rule Name
                </label>
                <input
                  type="text"
                  required
                  value={guidelineName}
                  onChange={(e) => setGuidelineName(e.target.value)}
                  placeholder="e.g. Prohibit Unsubstantiated Guarantees"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                    Severity
                  </label>
                  <select
                    value={guidelineSeverity}
                    onChange={(e) => setGuidelineSeverity(e.target.value as any)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                    Rule Engine
                  </label>
                  <select
                    value={guidelineRuleType}
                    onChange={(e) => setGuidelineRuleType(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper"
                  >
                    <option value="regex_match">Regex Pattern Match</option>
                    <option value="keyword_blacklist">Forbidden Keywords</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-ivory/80 uppercase tracking-wider">
                  Forbidden Patterns / Keywords (comma-separated)
                </label>
                <input
                  type="text"
                  required
                  value={guidelinePattern}
                  onChange={(e) => setGuidelinePattern(e.target.value)}
                  placeholder="guaranteed, 100% cure, unbeatable"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian border border-border-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-copper font-mono text-xs"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setAddGuidelineOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-secondary-text hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingGuideline}
                  className="px-5 py-2 rounded-xl bg-copper hover:bg-copper-highlight disabled:opacity-50 text-white font-semibold text-xs uppercase tracking-wider"
                >
                  {submittingGuideline ? 'Adding...' : 'Save Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
