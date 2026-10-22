/**
 * Inkloom Sentinel — TypeScript Domain & API Contracts
 */

export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_verified: boolean
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export type WorkspaceRole = 'owner' | 'admin' | 'reviewer' | 'contributor' | 'viewer'

export interface WorkspaceMember {
  id: string
  workspace_id: string
  user_id: string
  email: string
  role: WorkspaceRole
  is_active: boolean
  joined_at: string
}

export interface Workspace {
  id: string
  name: string
  slug: string
  description?: string | null
  created_at: string
  updated_at: string
}

export interface WorkspaceDetail extends Workspace {
  members: WorkspaceMember[]
  current_user_role?: WorkspaceRole
}

export type PolicyCategory = 'regulatory' | 'brand_voice' | 'claims_evidence' | 'content_safety' | 'editorial'

export type PolicyStatus = 'draft' | 'active' | 'deprecated' | 'archived'

export interface PolicyGuideline {
  id: string
  policy_id: string
  name: string
  description?: string
  category: PolicyCategory
  severity: 'low' | 'medium' | 'high' | 'critical'
  rule_type: string
  rule_config: Record<string, any>
  is_active: boolean
  created_at: string
}

export interface BrandPolicy {
  id: string
  workspace_id: string
  name: string
  slug: string
  description?: string | null
  category: PolicyCategory
  status: PolicyStatus
  version: number
  guidelines_count?: number
  created_at: string
  updated_at: string
}

export interface BrandPolicyDetail extends BrandPolicy {
  guidelines: PolicyGuideline[]
}

export type SubmissionStatus = 'draft' | 'in_review' | 'verified' | 'flagged' | 'rejected' | 'published'

export interface ContentRevision {
  id: string
  submission_id: string
  revision_number: number
  content_body: string
  content_format: string
  character_count: number
  word_count: number
  content_hash: string
  change_summary?: string | null
  author_id: string
  created_at: string
}

export interface ContentSubmission {
  id: string
  workspace_id: string
  title: string
  content_type: string
  status: SubmissionStatus
  current_revision_number: number
  revisions_count: number
  author_id: string
  created_at: string
  updated_at: string
}

export interface ContentSubmissionDetail extends ContentSubmission {
  revisions: ContentRevision[]
  current_revision?: ContentRevision
}

export interface RuleFinding {
  id: string
  guideline_id: string
  guideline_name?: string
  rule_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  passed: boolean
  matched_text?: string | null
  char_start?: number | null
  char_end?: number | null
  message: string
  recommendation?: string | null
}

export interface VerificationRun {
  id: string
  workspace_id: string
  submission_id: string
  revision_id: string
  revision_number: number
  policy_id: string
  policy_version: number
  status: 'running' | 'completed' | 'failed'
  passed: boolean
  findings_count: number
  violations_count: number
  rule_findings: RuleFinding[]
  executed_by_id: string
  created_at: string
}

export type EvidenceSourceType = 'internal_policy' | 'clinical_trial' | 'regulatory_filing' | 'scientific_paper' | 'legal_contract' | 'press_release'

export type SourceApprovalStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'revoked'

export interface EvidenceSource {
  id: string
  workspace_id: string
  title: string
  source_type: EvidenceSourceType
  source_url?: string | null
  internal_reference?: string | null
  publisher_or_owner: string
  approval_status: SourceApprovalStatus
  effective_date: string
  expiry_date?: string | null
  trusted_excerpts: string[]
  structured_facts: any[]
  is_valid?: boolean
  created_at: string
}

export type ClaimType = 'factual_assertion' | 'statistical_claim' | 'performance_guarantee' | 'regulatory_assertion' | 'comparative_superlative'

export type ClaimAssessmentStatus = 'supported' | 'contradicted' | 'insufficient_evidence' | 'conflicting_evidence' | 'needs_human_review'

export interface ClaimAssessment {
  id: string
  claim_id: string
  evidence_source_id?: string | null
  evidence_source_title?: string | null
  status: ClaimAssessmentStatus
  confidence_score: number
  supporting_excerpt?: string | null
  reasoning: string
  evaluated_at: string
}

export interface ContentClaim {
  id: string
  workspace_id: string
  revision_id: string
  claim_text: string
  claim_type: ClaimType
  context_excerpt?: string | null
  char_start?: number | null
  char_end?: number | null
  discovery_status: 'discovered' | 'confirmed' | 'dismissed'
  latest_assessment?: ClaimAssessment | null
  assessments?: ClaimAssessment[]
  created_at: string
}

export interface SemanticFinding {
  id: string
  guideline_id: string
  category: string
  outcome: 'pass' | 'violation' | 'needs_review' | 'inconclusive'
  explanation: string
  flagged_excerpt?: string | null
  char_start?: number | null
  char_end?: number | null
  confidence_score: number
  uncertainty_reason?: string | null
  recommendation?: string | null
  created_at: string
}

export interface SemanticReviewRun {
  id: string
  revision_id: string
  policy_id: string
  policy_version: number
  status: 'running' | 'completed' | 'failed'
  overall_outcome: string
  total_guidelines: number
  passed_count: number
  violation_count: number
  needs_review_count: number
  inconclusive_count: number
  findings: SemanticFinding[]
  execution_time_ms: number
  created_at: string
}

export interface CorrectionSuggestion {
  id: string
  workspace_id: string
  submission_id: string
  revision_id: string
  finding_id?: string | null
  status: 'proposed' | 'accepted' | 'rejected' | 'superseded'
  original_text: string
  proposed_replacement: string
  char_start: number
  char_end: number
  rationale: string
  proposed_by_id: string
  applied_revision_id?: string | null
  created_at: string
}

export interface ReviewDecision {
  id: string
  workspace_id: string
  submission_id: string
  revision_id: string
  decision: 'approved' | 'changes_requested' | 'rejected'
  comment?: string | null
  reviewer_id: string
  created_at: string
}

export interface UnifiedReviewSummary {
  workspace_id: string
  submission_id: string
  revision_id: string
  revision_number: number
  policy_id: string
  policy_version: number
  overall_status: 'pass' | 'action_required' | 'inconclusive' | 'incomplete' | 'needs_human_review'
  deterministic_run?: VerificationRun | null
  claims_assessed_count: number
  claims_supported_count: number
  claims_flagged_count: number
  claims: ContentClaim[]
  semantic_run?: SemanticReviewRun | null
  corrections: CorrectionSuggestion[]
  decisions: ReviewDecision[]
  can_approve: boolean
  approval_block_reason?: string | null
}

export interface AuditEvent {
  id: string
  event_type: string
  actor_id: string
  resource_type: string
  resource_id: string
  workspace_id?: string | null
  event_payload: Record<string, any>
  ip_address_hash?: string | null
  user_agent_snippet?: string | null
  created_at: string
  referenced_title?: string | null
  referenced_status?: string | null
}

export interface GovernanceAnalytics {
  workspace_id: string
  total_submissions: number
  total_revisions: number
  total_verifications: number
  total_claims_assessed: number
  policy_pass_rate: number
  avg_corrections_per_submission: number
  violation_breakdown: Record<string, number>
  decision_breakdown: Record<string, number>
  recent_activity_count: number
}
