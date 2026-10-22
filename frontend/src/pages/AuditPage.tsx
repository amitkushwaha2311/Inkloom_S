import React, { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import { AuditEvent } from '@/types/api'
import { Clock, Filter, Loader2, ShieldCheck, ChevronLeft, ChevronRight, Hash } from 'lucide-react'

export const AuditPage: React.FC = () => {
  const { activeWorkspace } = useAuth()
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [eventTypeFilter, setEventTypeFilter] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  const loadEvents = async () => {
    if (!activeWorkspace) return
    setLoading(true)
    try {
      const res = await api.audit.listEvents(activeWorkspace.id, {
        event_type: eventTypeFilter || undefined,
        page,
        page_size: 15,
      })
      setEvents(res.items || [])
      setTotalPages(res.total_pages || 1)
      setTotalCount(res.total || 0)
    } catch (err: any) {
      alert(err.message || 'Failed to load audit events')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEvents()
  }, [activeWorkspace, eventTypeFilter, page])

  const eventTypes = [
    'ALL',
    'USER_LOGIN',
    'WORKSPACE_CREATED',
    'POLICY_CREATED',
    'POLICY_ACTIVATED',
    'CONTENT_SUBMITTED',
    'CONTENT_REVISED',
    'VERIFICATION_RUN_COMPLETED',
    'EVIDENCE_SOURCE_REGISTERED',
    'EVIDENCE_SOURCE_APPROVED',
    'CLAIM_ASSESSED',
    'CORRECTION_SUGGESTED',
    'CORRECTION_APPLIED',
    'REVIEW_DECISION_RECORDED',
  ]

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border-dark">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-copper-highlight">
            Immutable Provenance
          </span>
          <h1 className="font-serif text-3xl text-paper-white tracking-tight">
            Workspace Audit Trail
          </h1>
          <p className="text-secondary-text text-xs mt-1">
            Append-only, chronologically indexed records of all governance and compliance mutations.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-secondary-text bg-charcoal px-3 py-2 rounded-xl border border-border-dark">
          <ShieldCheck className="w-4 h-4 text-chartreuse" />
          <span>Forensic Integrity: Active</span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="p-4 rounded-2xl bg-charcoal border border-border-dark flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <Filter className="w-4 h-4 text-secondary-text" />
          <span className="text-xs font-medium uppercase tracking-wider text-secondary-text">
            Filter Event Type:
          </span>
          <select
            value={eventTypeFilter}
            onChange={(e) => {
              setEventTypeFilter(e.target.value === 'ALL' ? '' : e.target.value)
              setPage(1)
            }}
            className="bg-obsidian text-ivory text-xs px-3 py-1.5 rounded-lg border border-border-dark focus:outline-none focus:ring-1 focus:ring-copper"
          >
            {eventTypes.map((t) => (
              <option key={t} value={t === 'ALL' ? '' : t}>
                {t.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        <div className="text-xs text-secondary-text font-mono">
          Showing {events.length} of {totalCount} total audit records
        </div>
      </div>

      {/* Audit Table */}
      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-4">
          <Loader2 className="w-8 h-8 animate-spin text-copper-highlight" />
          <span className="text-xs uppercase tracking-wider text-secondary-text">
            Querying audit log...
          </span>
        </div>
      ) : events.length === 0 ? (
        <div className="p-16 rounded-3xl bg-charcoal border border-border-dark text-center space-y-3">
          <Clock className="w-8 h-8 text-secondary-text mx-auto" />
          <h3 className="text-base font-medium text-paper-white">No audit records found</h3>
          <p className="text-xs text-secondary-text">
            Audit logs automatically record all workspace mutations, verification runs, and decisions.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-2xl bg-charcoal border border-border-dark overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-secondary text-secondary-text border-b border-border-dark font-medium uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Timestamp (UTC)</th>
                    <th className="py-3 px-4">Event Type</th>
                    <th className="py-3 px-4">Actor ID</th>
                    <th className="py-3 px-4">Resource Target</th>
                    <th className="py-3 px-4">Entity Context</th>
                    <th className="py-3 px-4">Forensic Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-dark text-ivory/90 font-mono text-[11px]">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-white/5 transition-colors">
                      <td className="py-3 px-4 text-secondary-text whitespace-nowrap">
                        {new Date(ev.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 font-sans font-semibold text-paper-white whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded text-[10px] bg-white/5 border border-white/10 uppercase">
                          {ev.event_type.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-copper-highlight truncate max-w-[120px]">
                        {ev.actor_id}
                      </td>
                      <td className="py-3 px-4 text-secondary-text">
                        {ev.resource_type} ({ev.resource_id.slice(0, 8)}...)
                      </td>
                      <td className="py-3 px-4 font-sans text-xs text-ivory">
                        {ev.referenced_title ? (
                          <span className="font-medium text-paper-white">{ev.referenced_title}</span>
                        ) : (
                          <span className="text-secondary-text italic text-[10px]">
                            {JSON.stringify(ev.event_payload).slice(0, 40)}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-secondary-text truncate max-w-[140px]">
                        {ev.ip_address_hash ? (
                          <span title={ev.ip_address_hash}>ip:{ev.ip_address_hash.slice(0, 10)}...</span>
                        ) : (
                          'n/a'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination Controls */}
          <div className="flex items-center justify-between px-2 pt-2 text-xs">
            <span className="text-secondary-text">
              Page {page} of {totalPages}
            </span>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg bg-charcoal border border-border-dark hover:bg-white/5 disabled:opacity-40 text-ivory flex items-center space-x-1 cursor-pointer"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-lg bg-charcoal border border-border-dark hover:bg-white/5 disabled:opacity-40 text-ivory flex items-center space-x-1 cursor-pointer"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
