/**
 * Inkloom Sentinel — Centralized API Client
 *
 * Implements token refresh rotation, workspace-scoped headers,
 * and standardized error parsing.
 */

import {
  AuthTokens,
  BrandPolicy,
  BrandPolicyDetail,
  ContentClaim,
  ContentSubmission,
  ContentSubmissionDetail,
  CorrectionSuggestion,
  EvidenceSource,
  GovernanceAnalytics,
  AuditEvent,
  ReviewDecision,
  SemanticReviewRun,
  UnifiedReviewSummary,
  User,
  VerificationRun,
  Workspace,
  WorkspaceDetail,
} from '@/types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

class ApiError extends Error {
  code: string
  status: number
  details?: Record<string, any>

  constructor(message: string, code: string = 'UNKNOWN_ERROR', status: number = 500, details?: Record<string, any>) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

class ApiClient {
  private accessToken: string | null = null
  private refreshToken: string | null = null
  private activeWorkspaceId: string | null = null
  private isRefreshing: boolean = false
  private refreshSubscribers: ((token: string) => void)[] = []

  constructor() {
    this.accessToken = localStorage.getItem('inkloom_access_token')
    this.refreshToken = localStorage.getItem('inkloom_refresh_token')
    this.activeWorkspaceId = localStorage.getItem('inkloom_active_workspace')
  }

  setTokens(tokens: AuthTokens | null) {
    if (tokens) {
      this.accessToken = tokens.access_token
      this.refreshToken = tokens.refresh_token
      localStorage.setItem('inkloom_access_token', tokens.access_token)
      localStorage.setItem('inkloom_refresh_token', tokens.refresh_token)
    } else {
      this.accessToken = null
      this.refreshToken = null
      localStorage.removeItem('inkloom_access_token')
      localStorage.removeItem('inkloom_refresh_token')
    }
  }

  setActiveWorkspaceId(id: string | null) {
    this.activeWorkspaceId = id
    if (id) {
      localStorage.setItem('inkloom_active_workspace', id)
    } else {
      localStorage.removeItem('inkloom_active_workspace')
    }
  }

  getActiveWorkspaceId(): string | null {
    return this.activeWorkspaceId
  }

  isAuthenticated(): boolean {
    return !!this.accessToken
  }

  private onTokenRefreshed(token: string) {
    this.refreshSubscribers.forEach((cb) => cb(token))
    this.refreshSubscribers = []
  }

  private addRefreshSubscriber(cb: (token: string) => void) {
    this.refreshSubscribers.push(cb)
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`
    }

    let response: Response
    try {
      response = await fetch(url, { ...options, headers })
    } catch (err: any) {
      throw new ApiError(
        err.message || 'Network error connecting to Sentinel API',
        'NETWORK_ERROR',
        0
      )
    }

    // Handle 401 and token refresh
    if (response.status === 401 && this.refreshToken && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
      if (!this.isRefreshing) {
        this.isRefreshing = true
        try {
          const newTokens = await this.auth.refresh(this.refreshToken)
          this.setTokens(newTokens)
          this.isRefreshing = false
          this.onTokenRefreshed(newTokens.access_token)
        } catch {
          this.isRefreshing = false
          this.setTokens(null)
          throw new ApiError('Session expired. Please sign in again.', 'SESSION_EXPIRED', 401)
        }
      }

      // Wait for ongoing refresh
      return new Promise<T>((resolve, reject) => {
        this.addRefreshSubscriber(async (newToken: string) => {
          headers['Authorization'] = `Bearer ${newToken}`
          try {
            const retryResp = await fetch(url, { ...options, headers })
            if (!retryResp.ok) {
              const errData = await retryResp.json().catch(() => ({}))
              reject(new ApiError(errData?.error?.message || 'Request failed', errData?.error?.code, retryResp.status))
            } else {
              const data = retryResp.status === 204 ? ({} as T) : await retryResp.json()
              resolve(data)
            }
          } catch (err) {
            reject(err)
          }
        })
      })
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      const code = errData?.error?.code || 'ERROR'
      const message = errData?.error?.message || `Request failed with status ${response.status}`
      const details = errData?.error?.details
      throw new ApiError(message, code, response.status, details)
    }

    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  }

  // -------------------------------------------------------------------------
  // Auth API
  // -------------------------------------------------------------------------
  auth = {
    register: (data: { email: string; password: string; full_name: string }) =>
      this.request<User>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    login: async (data: { email: string; password: string }) => {
      const res = await this.request<AuthTokens>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      this.setTokens(res)
      return res
    },

    refresh: (refreshToken: string) =>
      this.request<AuthTokens>('/api/v1/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      }),

    logout: async () => {
      if (this.refreshToken) {
        try {
          await this.request<void>('/api/v1/auth/logout', {
            method: 'POST',
            body: JSON.stringify({ refresh_token: this.refreshToken }),
          })
        } catch {
          // Ignore logout error if token already revoked
        }
      }
      this.setTokens(null)
      this.setActiveWorkspaceId(null)
    },

    me: () => this.request<User>('/api/v1/auth/me'),

    changePassword: (data: { current_password: string; new_password: string }) =>
      this.request<void>('/api/v1/auth/me/password', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  }

  // -------------------------------------------------------------------------
  // Workspaces API
  // -------------------------------------------------------------------------
  workspaces = {
    // Backend returns a plain array — wrap it into the paginated envelope the
    // context expects so both sides stay consistent.
    list: async (): Promise<{ items: Workspace[]; total: number }> => {
      const arr = await this.request<Workspace[]>('/api/v1/workspaces')
      return { items: Array.isArray(arr) ? arr : [], total: Array.isArray(arr) ? arr.length : 0 }
    },

    get: (id: string) => this.request<WorkspaceDetail>(`/api/v1/workspaces/${id}`),

    create: (data: { name: string; description?: string }) =>
      this.request<Workspace>('/api/v1/workspaces', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: string, data: { name?: string; description?: string }) =>
      this.request<Workspace>(`/api/v1/workspaces/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    addMember: (workspaceId: string, data: { email: string; role: string }) =>
      this.request<any>(`/api/v1/workspaces/${workspaceId}/members`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    removeMember: (workspaceId: string, memberId: string) =>
      this.request<void>(`/api/v1/workspaces/${workspaceId}/members/${memberId}`, {
        method: 'DELETE',
      }),
  }

  // -------------------------------------------------------------------------
  // Brand Policies API
  // -------------------------------------------------------------------------
  policies = {
    list: (workspaceId: string) =>
      this.request<{ items: BrandPolicy[]; total: number }>(`/api/v1/workspaces/${workspaceId}/policies`),

    get: (workspaceId: string, policyId: string) =>
      this.request<BrandPolicyDetail>(`/api/v1/workspaces/${workspaceId}/policies/${policyId}`),

    create: (workspaceId: string, data: { name: string; description?: string; category: string }) =>
      this.request<BrandPolicy>(`/api/v1/workspaces/${workspaceId}/policies`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    activate: (workspaceId: string, policyId: string) =>
      this.request<BrandPolicy>(`/api/v1/workspaces/${workspaceId}/policies/${policyId}/activate`, {
        method: 'POST',
      }),

    deprecate: (workspaceId: string, policyId: string) =>
      this.request<BrandPolicy>(`/api/v1/workspaces/${workspaceId}/policies/${policyId}/deprecate`, {
        method: 'POST',
      }),

    addGuideline: (
      workspaceId: string,
      policyId: string,
      data: {
        name: string
        description?: string
        category: string
        severity: string
        rule_type: string
        rule_config: Record<string, any>
      }
    ) =>
      this.request<any>(`/api/v1/workspaces/${workspaceId}/policies/${policyId}/guidelines`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    deleteGuideline: (workspaceId: string, policyId: string, guidelineId: string) =>
      this.request<void>(`/api/v1/workspaces/${workspaceId}/policies/${policyId}/guidelines/${guidelineId}`, {
        method: 'DELETE',
      }),
  }

  // -------------------------------------------------------------------------
  // Content Submissions & Revisions API
  // -------------------------------------------------------------------------
  submissions = {
    list: (workspaceId: string, params?: { status?: string }) => {
      const q = params?.status ? `?status=${params.status}` : ''
      return this.request<{ items: ContentSubmission[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions${q}`
      )
    },

    get: (workspaceId: string, submissionId: string) =>
      this.request<ContentSubmissionDetail>(`/api/v1/workspaces/${workspaceId}/submissions/${submissionId}`),

    create: (
      workspaceId: string,
      data: { title: string; content_type: string; initial_content: string; tags?: string[] }
    ) =>
      this.request<ContentSubmissionDetail>(`/api/v1/workspaces/${workspaceId}/submissions`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    addRevision: (
      workspaceId: string,
      submissionId: string,
      data: { content_body: string; change_summary?: string }
    ) =>
      this.request<any>(`/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  }

  // -------------------------------------------------------------------------
  // Deterministic Verification API
  // -------------------------------------------------------------------------
  verification = {
    run: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      data: { policy_id: string }
    ) =>
      this.request<VerificationRun>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/verification/runs?revision_number=${revisionNumber}`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),

    listRuns: (workspaceId: string, submissionId: string) =>
      this.request<{ items: VerificationRun[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/verification/runs`
      ),
  }

  // -------------------------------------------------------------------------
  // Evidence Sources & Claims API
  // -------------------------------------------------------------------------
  evidence = {
    listSources: (workspaceId: string) =>
      this.request<{ items: EvidenceSource[]; total: number }>(`/api/v1/workspaces/${workspaceId}/evidence-sources`),

    createSource: (
      workspaceId: string,
      data: {
        title: string
        source_type: string
        source_url?: string
        internal_reference?: string
        publisher_or_owner: string
        effective_date: string
        expiry_date?: string
        trusted_excerpts?: string[]
        structured_facts?: any[]
      }
    ) =>
      this.request<EvidenceSource>(`/api/v1/workspaces/${workspaceId}/evidence-sources`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    approveSource: (workspaceId: string, sourceId: string) =>
      this.request<EvidenceSource>(`/api/v1/workspaces/${workspaceId}/evidence-sources/${sourceId}/approve`, {
        method: 'POST',
      }),

    rejectSource: (workspaceId: string, sourceId: string, reason: string) =>
      this.request<EvidenceSource>(`/api/v1/workspaces/${workspaceId}/evidence-sources/${sourceId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }),

    revokeSource: (workspaceId: string, sourceId: string, reason: string) =>
      this.request<EvidenceSource>(`/api/v1/workspaces/${workspaceId}/evidence-sources/${sourceId}/revoke`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      }),

    discoverClaims: (workspaceId: string, submissionId: string, revisionNumber: number) =>
      this.request<{ claims: ContentClaim[]; discovered_count: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/claims/discover`,
        { method: 'POST' }
      ),

    listClaims: (workspaceId: string, submissionId: string, revisionNumber: number) =>
      this.request<{ items: ContentClaim[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/claims`
      ),

    createClaim: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      data: { claim_text: string; claim_type: string; context_excerpt?: string }
    ) =>
      this.request<ContentClaim>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/claims`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),

    assessClaim: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      claimId: string,
      evidenceSourceId?: string
    ) =>
      this.request<any>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/claims/${claimId}/assess`,
        {
          method: 'POST',
          body: JSON.stringify({ evidence_source_id: evidenceSourceId }),
        }
      ),
  }

  // -------------------------------------------------------------------------
  // Semantic Review API
  // -------------------------------------------------------------------------
  semantic = {
    run: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      data: { policy_id: string }
    ) =>
      this.request<SemanticReviewRun>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/semantic-review/runs`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),

    listRuns: (workspaceId: string, submissionId: string, revisionNumber: number) =>
      this.request<{ items: SemanticReviewRun[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/semantic-review/runs`
      ),
  }

  // -------------------------------------------------------------------------
  // Unified Review Orchestration & Governance API
  // -------------------------------------------------------------------------
  reviews = {
    getSummary: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      policyId: string
    ) =>
      this.request<UnifiedReviewSummary>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/review-summary?policy_id=${policyId}`
      ),

    listCorrections: (workspaceId: string, submissionId: string, revisionNumber: number) =>
      this.request<{ items: CorrectionSuggestion[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/corrections`
      ),

    proposeCorrection: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      data: {
        original_text: string
        proposed_replacement: string
        char_start: number
        char_end: number
        rationale: string
        finding_id?: string
      }
    ) =>
      this.request<CorrectionSuggestion>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/corrections`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),

    applyCorrection: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      correctionId: string
    ) =>
      this.request<{ correction: CorrectionSuggestion; new_revision: any }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/corrections/${correctionId}/apply`,
        { method: 'POST' }
      ),

    listDecisions: (workspaceId: string, submissionId: string, revisionNumber: number) =>
      this.request<{ items: ReviewDecision[]; total: number }>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/decisions`
      ),

    recordDecision: (
      workspaceId: string,
      submissionId: string,
      revisionNumber: number,
      data: { decision: 'approved' | 'changes_requested' | 'rejected'; comment?: string }
    ) =>
      this.request<ReviewDecision>(
        `/api/v1/workspaces/${workspaceId}/submissions/${submissionId}/revisions/${revisionNumber}/decisions`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      ),
  }

  // -------------------------------------------------------------------------
  // Audit Trail & Governance Analytics API
  // -------------------------------------------------------------------------
  audit = {
    listEvents: (
      workspaceId: string,
      params?: {
        event_type?: string
        actor_id?: string
        submission_id?: string
        page?: number
        page_size?: number
      }
    ) => {
      const sp = new URLSearchParams()
      if (params?.event_type) sp.append('event_type', params.event_type)
      if (params?.actor_id) sp.append('actor_id', params.actor_id)
      if (params?.submission_id) sp.append('submission_id', params.submission_id)
      if (params?.page) sp.append('page', params.page.toString())
      if (params?.page_size) sp.append('page_size', params.page_size.toString())
      const qs = sp.toString() ? `?${sp.toString()}` : ''
      return this.request<{ items: AuditEvent[]; total: number; page: number; total_pages: number }>(
        `/api/v1/workspaces/${workspaceId}/audit-events${qs}`
      )
    },

    getAnalytics: (workspaceId: string) =>
      this.request<GovernanceAnalytics>(`/api/v1/workspaces/${workspaceId}/analytics`),
  }
}

export const api = new ApiClient()
export { ApiError }
