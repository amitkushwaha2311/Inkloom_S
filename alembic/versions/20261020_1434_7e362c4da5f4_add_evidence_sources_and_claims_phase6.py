"""add_evidence_sources_and_claims_phase6

Revision ID: 7e362c4da5f4
Revises: 92f9f28f0797
Create Date: 2026-10-20 14:34:29.813913+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e362c4da5f4'
down_revision: Union[str, None] = '92f9f28f0797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. evidence_sources
    op.create_table(
        'evidence_sources',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('internal_reference', sa.String(length=255), nullable=True),
        sa.Column('publisher_or_owner', sa.String(length=255), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('trusted_excerpts', sa.JSON(), nullable=False),
        sa.Column('structured_facts', sa.JSON(), nullable=False),
        sa.Column('created_by_id', sa.String(length=64), nullable=False),
        sa.Column('approved_by_id', sa.String(length=64), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['brand_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evidence_sources_workspace_id'), 'evidence_sources', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_evidence_sources_source_type'), 'evidence_sources', ['source_type'], unique=False)
    op.create_index(op.f('ix_evidence_sources_approval_status'), 'evidence_sources', ['approval_status'], unique=False)

    # 2. content_claims
    op.create_table(
        'content_claims',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('revision_id', sa.Uuid(), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.String(length=32), nullable=False),
        sa.Column('context_excerpt', sa.Text(), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['revision_id'], ['content_revisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['brand_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_claims_workspace_id'), 'content_claims', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_content_claims_revision_id'), 'content_claims', ['revision_id'], unique=False)
    op.create_index(op.f('ix_content_claims_claim_type'), 'content_claims', ['claim_type'], unique=False)

    # 3. claim_assessments
    op.create_table(
        'claim_assessments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('claim_id', sa.Uuid(), nullable=False),
        sa.Column('revision_id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('policy_id', sa.Uuid(), nullable=True),
        sa.Column('policy_version', sa.Integer(), nullable=True),
        sa.Column('assessment_status', sa.String(length=32), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('uncertainty_score', sa.Float(), nullable=True),
        sa.Column('engine_version', sa.String(length=64), nullable=False),
        sa.Column('assessed_by_id', sa.String(length=64), nullable=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('supporting_sources_snapshot', sa.JSON(), nullable=False),
        sa.Column('contradicting_sources_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['content_claims.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['policy_id'], ['brand_policies.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revision_id'], ['content_revisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['brand_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_claim_assessments_claim_id'), 'claim_assessments', ['claim_id'], unique=False)
    op.create_index(op.f('ix_claim_assessments_revision_id'), 'claim_assessments', ['revision_id'], unique=False)
    op.create_index(op.f('ix_claim_assessments_workspace_id'), 'claim_assessments', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_claim_assessments_policy_id'), 'claim_assessments', ['policy_id'], unique=False)
    op.create_index(op.f('ix_claim_assessments_assessment_status'), 'claim_assessments', ['assessment_status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_claim_assessments_assessment_status'), table_name='claim_assessments')
    op.drop_index(op.f('ix_claim_assessments_policy_id'), table_name='claim_assessments')
    op.drop_index(op.f('ix_claim_assessments_workspace_id'), table_name='claim_assessments')
    op.drop_index(op.f('ix_claim_assessments_revision_id'), table_name='claim_assessments')
    op.drop_index(op.f('ix_claim_assessments_claim_id'), table_name='claim_assessments')
    op.drop_table('claim_assessments')

    op.drop_index(op.f('ix_content_claims_claim_type'), table_name='content_claims')
    op.drop_index(op.f('ix_content_claims_revision_id'), table_name='content_claims')
    op.drop_index(op.f('ix_content_claims_workspace_id'), table_name='content_claims')
    op.drop_table('content_claims')

    op.drop_index(op.f('ix_evidence_sources_approval_status'), table_name='evidence_sources')
    op.drop_index(op.f('ix_evidence_sources_source_type'), table_name='evidence_sources')
    op.drop_index(op.f('ix_evidence_sources_workspace_id'), table_name='evidence_sources')
    op.drop_table('evidence_sources')
