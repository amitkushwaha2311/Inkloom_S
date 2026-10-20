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


class AuditEventType(str, Enum):
    """Types of immutable events captured in the audit trail."""
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_MEMBER_ADDED = "workspace_member_added"
    POLICY_CREATED = "policy_created"
    POLICY_PUBLISHED = "policy_published"
    POLICY_DEPRECATED = "policy_deprecated"
    CONTENT_SUBMITTED = "content_submitted"
    CONTENT_REVISED = "content_revised"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    REVIEW_DECIDED = "review_decided"
    AUDIT_EXPORTED = "audit_exported"
