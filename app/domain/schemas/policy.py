"""Inkloom Sentinel - Brand Policy & Guideline Pydantic Schemas.

Request and response DTOs for policy CRUD, versioning, and guideline ingestion.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.enums import FindingCategory, PolicyStatus, SeverityLevel

# ---------------------------------------------------------------------------
# Guideline schemas
# ---------------------------------------------------------------------------


class GuidelineCreate(BaseModel):
    """Input schema for adding a single guideline to a policy draft."""

    category: FindingCategory = Field(..., description="Compliance category for this rule")
    title: Annotated[str, Field(min_length=3, max_length=200, description="Short rule label")]
    rule_text: Annotated[
        str, Field(min_length=10, max_length=5000, description="Precise, verifiable rule statement")
    ]
    examples_approved: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Approved example phrases (max 20 items)",
    )
    examples_prohibited: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Prohibited example phrases (max 20 items)",
    )
    severity_default: SeverityLevel = Field(
        SeverityLevel.MEDIUM, description="Default severity when this rule is violated"
    )
    is_mandatory: bool = Field(True, description="Whether this rule is non-waivable")
    rule_config: dict = Field(
        default_factory=dict,
        description="Structured deterministic rule configuration (e.g. rule_type, terms, etc.)",
    )

    @field_validator("rule_config")
    @classmethod
    def validate_rule_config(cls, v: dict) -> dict:
        if not v:
            return v
        rule_type = v.get("rule_type")
        if rule_type is not None:
            supported = {
                "prohibited_terms",
                "required_terms",
                "brand_spelling",
                "length_limit",
                "semantic",
                "superlatives",
                "tone",
                "human_review",
            }
            if rule_type not in supported:
                raise ValueError(
                    f"Unsupported rule_type '{rule_type}'. Supported rule types: {sorted(supported)}"
                )
            if rule_type in ("prohibited_terms", "required_terms"):
                terms = v.get("terms")
                if terms is not None:
                    if not isinstance(terms, list) or len(terms) == 0:
                        raise ValueError(
                            f"rule_type '{rule_type}' requires a non-empty 'terms' list."
                        )
                    for t in terms:
                        if not isinstance(t, str) or not t.strip():
                            raise ValueError(
                                f"rule_type '{rule_type}' terms items must be non-empty strings."
                            )
            elif rule_type == "brand_spelling":
                canonical = v.get("canonical_name")
                if not canonical or not isinstance(canonical, str) or not canonical.strip():
                    raise ValueError(
                        "brand_spelling rule requires a non-empty 'canonical_name' string."
                    )
            elif rule_type == "length_limit":
                min_c = v.get("min_count")
                max_c = v.get("max_count")
                if min_c is None and max_c is None:
                    raise ValueError(
                        "length_limit rule requires at least one of 'min_count' or 'max_count'."
                    )
        return v

    @field_validator("examples_approved", "examples_prohibited", mode="before")
    @classmethod
    def validate_example_items(cls, v: list) -> list:
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Each example must be a string")
            if len(item.strip()) == 0:
                raise ValueError("Example items must not be blank strings")
            if len(item) > 500:
                raise ValueError("Each example item must be 500 characters or fewer")
        return v

    @model_validator(mode="after")
    def rule_text_must_not_match_title_only(self) -> "GuidelineCreate":
        """Prevent rule_text from just repeating the title without substance."""
        if self.rule_text.strip().lower() == self.title.strip().lower():
            raise ValueError("rule_text must provide substance beyond the title")
        return self


class GuidelineUpdate(BaseModel):
    """Input schema for updating an existing guideline on a DRAFT policy."""

    category: FindingCategory | None = None
    title: Annotated[str, Field(min_length=3, max_length=200)] | None = None
    rule_text: Annotated[str, Field(min_length=10, max_length=5000)] | None = None
    examples_approved: list[str] | None = None
    examples_prohibited: list[str] | None = None
    severity_default: SeverityLevel | None = None
    is_mandatory: bool | None = None
    rule_config: dict | None = None

    @field_validator("examples_approved", "examples_prohibited", mode="before")
    @classmethod
    def validate_example_items(cls, v: list | None) -> list | None:
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Each example must be a string")
            if len(item.strip()) == 0:
                raise ValueError("Example items must not be blank strings")
            if len(item) > 500:
                raise ValueError("Each example item must be 500 characters or fewer")
        return v


class GuidelineResponse(BaseModel):
    """Response schema for a policy guideline."""

    id: uuid.UUID
    policy_id: uuid.UUID
    category: FindingCategory
    title: str
    rule_text: str
    examples_approved: list[str]
    examples_prohibited: list[str]
    severity_default: SeverityLevel
    is_mandatory: bool
    rule_config: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Policy schemas
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    """Input schema for creating a new brand policy (always starts as DRAFT version 1)."""

    name: Annotated[str, Field(min_length=2, max_length=160, description="Policy display name")]
    description: Annotated[str, Field(max_length=500)] | None = Field(
        None, description="Optional short description"
    )
    guidelines: list[GuidelineCreate] = Field(
        default_factory=list,
        max_length=100,
        description="Optional initial guidelines (max 100)",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Policy name must not be blank or whitespace only")
        return v.strip()


class PolicyUpdate(BaseModel):
    """Input schema for updating metadata of a DRAFT policy.

    Updating an ACTIVE policy is not permitted; callers must create a new version.
    """

    name: Annotated[str, Field(min_length=2, max_length=160)] | None = None
    description: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Policy name must not be blank or whitespace only")
        return v.strip() if v else v


class PolicyResponse(BaseModel):
    """Response schema for a single policy (without inline guidelines)."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    version: int
    status: PolicyStatus
    created_by_id: str
    created_at: datetime
    updated_at: datetime
    guideline_count: int = Field(0, description="Number of guidelines in this policy version")

    model_config = {"from_attributes": True}


class PolicyDetailResponse(PolicyResponse):
    """Full policy response including all guidelines."""

    guidelines: list[GuidelineResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    """Paginated list of policies."""

    items: list[PolicyResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class PolicyVersionHistoryItem(BaseModel):
    """Summary of a single policy version for history listing."""

    id: uuid.UUID
    version: int
    status: PolicyStatus
    created_by_id: str
    created_at: datetime
    updated_at: datetime
    guideline_count: int

    model_config = {"from_attributes": True}


class PolicyVersionHistoryResponse(BaseModel):
    """Full version history for a named policy within a workspace."""

    workspace_id: uuid.UUID
    policy_name: str
    versions: list[PolicyVersionHistoryItem]


class PolicyActivateRequest(BaseModel):
    """Request body for explicitly activating a DRAFT policy.

    Activating a policy requires at least one guideline to be present.
    Caller must confirm this is intentional.
    """

    confirm: bool = Field(
        ...,
        description="Must be true to confirm intentional activation",
    )

    @field_validator("confirm")
    @classmethod
    def must_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError("confirm must be true to activate a policy")
        return v


class PolicyDeprecateRequest(BaseModel):
    """Request body for deprecating an ACTIVE policy version."""

    reason: Annotated[
        str, Field(min_length=5, max_length=500, description="Reason for deprecation")
    ]

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Deprecation reason must not be blank or whitespace only")
        return v.strip()
