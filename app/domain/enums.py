"""Inkloom Sentinel - Domain Enumerations.

Defines standardized vocabulary and statuses across all domain boundaries.
"""

from enum import Enum


class WorkspaceRole(str, Enum):
    """Access tier for brand workspace collaborators."""

    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class PolicyStatus(str, Enum):
    """Lifecycle state of a brand policy version."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class FindingCategory(str, Enum):
    """Classification of verification findings."""

    BRAND_VOICE = "brand_voice"
    TONE_CONSISTENCY = "tone_consistency"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    TERMINOLOGY = "terminology"
    FACTUAL_ACCURACY = "factual_accuracy"
    RESTRICTED_CLAIMS = "restricted_claims"


class SeverityLevel(str, Enum):
    """Impact severity assigned to a verification finding or rule violation."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SubmissionStatus(str, Enum):
    """Lifecycle state of a content draft submitted for verification."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceReferenceType(str, Enum):
    """Classification of evidence backing a verification finding."""

    POLICY_CLAUSE = "policy_clause"
    REGULATORY_STANDARD = "regulatory_standard"
    APPROVED_LEXICON = "approved_lexicon"
    CITATION = "citation"


class ReviewDecisionType(str, Enum):
    """Final decision rendered by a brand reviewer."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class ContentType(str, Enum):
    """Supported text asset categories for content ingestion."""

    MARKETING_COPY = "marketing_copy"
    LANDING_PAGE = "landing_page"
    SOCIAL_MEDIA_POST = "social_media_post"
    PRODUCT_DESCRIPTION = "product_description"
    EMAIL_COPY = "email_copy"
    CAMPAIGN_MESSAGING = "campaign_messaging"
    OTHER = "other"


class AuditEventType(str, Enum):
    """Types of immutable events captured in the audit trail."""

    # Account lifecycle
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LOGOUT = "user_logout"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REVOKED = "token_revoked"
    PASSWORD_CHANGED = "password_changed"
    # Workspace management
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_MEMBER_ADDED = "workspace_member_added"
    WORKSPACE_MEMBER_ROLE_CHANGED = "workspace_member_role_changed"
    WORKSPACE_MEMBER_REMOVED = "workspace_member_removed"
    # Policy lifecycle
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_PUBLISHED = "policy_published"
    POLICY_DEPRECATED = "policy_deprecated"
    POLICY_ARCHIVED = "policy_archived"
    # Guideline management
    GUIDELINE_ADDED = "guideline_added"
    GUIDELINE_UPDATED = "guideline_updated"
    GUIDELINE_DELETED = "guideline_deleted"
    # Content & verification
    CONTENT_SUBMITTED = "content_submitted"
    CONTENT_REVISED = "content_revised"
    CONTENT_METADATA_UPDATED = "content_metadata_updated"
    CONTENT_STATUS_CHANGED = "content_status_changed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    REVIEW_DECIDED = "review_decided"
    AUDIT_EXPORTED = "audit_exported"
    # Phase 6: Evidence & Claims
    EVIDENCE_SOURCE_CREATED = "evidence_source_created"
    EVIDENCE_SOURCE_UPDATED = "evidence_source_updated"
    EVIDENCE_SOURCE_APPROVED = "evidence_source_approved"
    EVIDENCE_SOURCE_REJECTED = "evidence_source_rejected"
    EVIDENCE_SOURCE_REVOKED = "evidence_source_revoked"
    CLAIM_RECORDED = "claim_recorded"
    CLAIM_ASSESSED = "claim_assessed"
    # Phase 7: Semantic Review & Claim Discovery
    CLAIMS_DISCOVERED = "claims_discovered"
    CLAIM_UPDATED = "claim_updated"
    SEMANTIC_REVIEW_STARTED = "semantic_review_started"
    SEMANTIC_REVIEW_COMPLETED = "semantic_review_completed"
    # Phase 8: Unified Review & Corrections
    CORRECTION_SUGGESTION_CREATED = "correction_suggestion_created"
    CORRECTION_SUGGESTION_UPDATED = "correction_suggestion_updated"
    CORRECTION_APPLIED = "correction_applied"
    REVIEW_DECISION_RECORDED = "review_decision_recorded"


class EvidenceSourceType(str, Enum):
    """Categorization of authoritative evidence sources."""

    SCIENTIFIC_STUDY = "scientific_study"
    REGULATORY_FILING = "regulatory_filing"
    PRODUCT_SPECIFICATION = "product_specification"
    CERTIFIED_LAB_RESULT = "certified_lab_result"
    INTERNAL_BENCHMARK = "internal_benchmark"
    PRESS_RELEASE = "press_release"
    OTHER = "other"


class SourceApprovalStatus(str, Enum):
    """Approval lifecycle of an evidence source."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class ClaimType(str, Enum):
    """Classification of content claims."""

    FACTUAL = "factual"
    OPINION = "opinion"
    PROMOTIONAL = "promotional"


class ClaimDiscoveryStatus(str, Enum):
    """Human review and discovery state of an extracted claim."""

    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    EDITED = "edited"


class ClaimAssessmentStatus(str, Enum):
    """Conservative verification assessment of a claim against approved evidence."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class SemanticOutcome(str, Enum):
    """Explicit assessment result of a semantic guideline evaluation."""

    PASS = "pass"
    VIOLATION = "violation"
    NEEDS_REVIEW = "needs_review"
    INCONCLUSIVE = "inconclusive"


class CorrectionStatus(str, Enum):
    """Lifecycle status of a structured correction suggestion."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class UnifiedCheckStatus(str, Enum):
    """Execution status of an individual verification component check."""

    NOT_RUN = "not_run"
    COMPLETED = "completed"
    FAILED = "failed"


class UnifiedReviewOutcome(str, Enum):
    """Synthesized overall review outcome across all checks."""

    PASS = "pass"
    ACTION_REQUIRED = "action_required"
    INCONCLUSIVE = "inconclusive"
    INCOMPLETE = "incomplete"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
