import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import { GovernanceAnalytics } from '@/types/api'
import { BarChart3, Loader2, ShieldCheck, AlertCircle, FileCheck, Layers, PieChart } from 'lucide-react'

export const AnalyticsPage: React.FC = () => {
  const { activeWorkspace } = useAuth()
  const [analytics, setAnalytics] = useState<GovernanceAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeWorkspace) return
    const loadAnalytics = async () => {
      setLoading(true)
      try {
        const res = await api.audit.getAnalytics(activeWorkspace.id)
        setAnalytics(res)
      } catch (err: any) {
        alert(err.message || 'Failed to load analytics')
      } finally {
        setLoading(false)
      }
    }
    loadAnalytics()
  }, [activeWorkspace])

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
        <span className="text-xs uppercase tracking-wider text-secondary-text">
          Computing governance analytics...
        </span>
      </div>
    )
  }

  const passRatePct =
    analytics && analytics.policy_pass_rate !== undefined
      ? Math.round(analytics.policy_pass_rate * 100)
      : 0

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Operational Telemetry
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Governance & Compliance Analytics
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Data-backed metrics across deterministic engines, claim proofs, and reviewer outcomes.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-secondary-text bg-charcoal px-3 py-2 rounded-xl border border-border-dark">
          <BarChart3 className="w-4 h-4 text-copper-highlight" />
          <span>Real-time Workspace Aggregation</span>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
          <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
            Total Content Submissions
          </span>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.total_submissions || 0}
          </div>
          <div className="text-[11px] text-secondary-text">
            {analytics?.total_revisions || 0} total revisions committed
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
          <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
            Verification Runs
          </span>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.total_verifications || 0}
          </div>
          <div className="text-[11px] text-secondary-text">
            Automated deterministic executions
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
          <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
            Claims Evaluated
          </span>
          <div className="text-3xl font-serif text-paper-white font-bold">
            {analytics?.total_claims_assessed || 0}
          </div>
          <div className="text-[11px] text-secondary-text">
            Evaluated against authoritative sources
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-charcoal border border-border-dark space-y-3 shadow-lg">
          <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
            Deterministic Pass Rate
          </span>
          <div className="text-3xl font-serif text-chartreuse font-bold">
            {passRatePct}%
          </div>
          <div className="w-full bg-obsidian h-1.5 rounded-full overflow-hidden mt-1">
            <div
              className="bg-chartreuse h-full rounded-full transition-all duration-500"
              style={{ width: `${passRatePct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Breakdowns Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 text-left">
        {/* Violation Category Breakdown */}
        <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 shadow-xl">
          <div className="space-y-1 border-b border-border-dark pb-4">
            <h3 className="font-serif text-xl text-paper-white">Violations by Policy Category</h3>
            <p className="text-xs text-secondary-text">
              Distribution of non-compliant findings across guideline classifications.
            </p>
          </div>

          {!analytics?.violation_breakdown ||
          Object.keys(analytics.violation_breakdown).length === 0 ? (
            <div className="py-12 text-center text-xs text-secondary-text">
              No guideline violations recorded in this workspace. Zero non-compliance detected.
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(analytics.violation_breakdown).map(([cat, count]) => (
                <div key={cat} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-paper-white capitalize">
                      {cat.replace('_', ' ')}
                    </span>
                    <span className="font-mono text-copper-highlight font-bold">{count}</span>
                  </div>
                  <div className="w-full bg-obsidian h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-copper h-full rounded-full"
                      style={{
                        width: `${Math.min(100, (count / (analytics.total_verifications || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Governance Decisions Breakdown */}
        <div className="p-6 sm:p-8 rounded-3xl bg-charcoal border border-border-dark space-y-6 shadow-xl">
          <div className="space-y-1 border-b border-border-dark pb-4">
            <h3 className="font-serif text-xl text-paper-white">Reviewer Determination Outcomes</h3>
            <p className="text-xs text-secondary-text">
              Outcomes recorded by authorized reviewers with separation of duties enforcement.
            </p>
          </div>

          {!analytics?.decision_breakdown ||
          Object.keys(analytics.decision_breakdown).length === 0 ? (
            <div className="py-12 text-center text-xs text-secondary-text">
              No formal governance decisions recorded yet. Complete reviews in the Unified Review console.
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(analytics.decision_breakdown).map(([decision, count]) => (
                <div
                  key={decision}
                  className="p-4 rounded-xl bg-obsidian border border-border-dark flex items-center justify-between text-xs"
                >
                  <span className="font-semibold uppercase tracking-wider text-paper-white">
                    {decision.replace('_', ' ')}
                  </span>
                  <span
                    className={`px-3 py-1 rounded-full font-mono font-bold text-xs ${
                      decision === 'approved'
                        ? 'bg-chartreuse/20 text-chartreuse border border-chartreuse/30'
                        : decision === 'rejected'
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                        : 'bg-copper/20 text-copper-highlight border border-copper/30'
                    }`}
                  >
                    {count} records
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
