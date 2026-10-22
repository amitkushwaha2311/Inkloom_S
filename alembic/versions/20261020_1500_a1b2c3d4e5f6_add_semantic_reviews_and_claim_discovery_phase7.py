"""add_semantic_reviews_and_claim_discovery_phase7

Revision ID: a1b2c3d4e5f6
Revises: 7e362c4da5f4
Create Date: 2026-10-20 15:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7e362c4da5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update content_claims with discovery and review metadata
    with op.batch_alter_table('content_claims') as batch_op:
        batch_op.add_column(
            sa.Column('discovery_status', sa.String(length=32), server_default='candidate', nullable=False)
        )
        batch_op.add_column(
            sa.Column('extraction_method', sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column('extraction_version', sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column('reviewed_by_id', sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            batch_op.f('ix_content_claims_discovery_status'), ['discovery_status'], unique=False
        )

    # 2. Create semantic_review_runs table
    op.create_table(
        'semantic_review_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('revision_id', sa.Uuid(), nullable=False),
        sa.Column('policy_id', sa.Uuid(), nullable=False),
        sa.Column('policy_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='completed', nullable=False),
        sa.Column('overall_outcome', sa.String(length=32), nullable=False),
        sa.Column('total_guidelines', sa.Integer(), server_default='0', nullable=False),
        sa.Column('passed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('violation_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('needs_review_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('inconclusive_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('executed_by_id', sa.String(length=64), nullable=False),
        sa.Column('engine_version', sa.String(length=64), server_default='sentinel-semantic-v1.0', nullable=False),
        sa.Column('execution_time_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['brand_policies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['revision_id'], ['content_revisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['brand_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_semantic_review_runs_workspace_id'), 'semantic_review_runs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_semantic_review_runs_revision_id'), 'semantic_review_runs', ['revision_id'], unique=False)
    op.create_index(op.f('ix_semantic_review_runs_policy_id'), 'semantic_review_runs', ['policy_id'], unique=False)
    op.create_index(op.f('ix_semantic_review_runs_overall_outcome'), 'semantic_review_runs', ['overall_outcome'], unique=False)

    # 3. Create semantic_review_findings table
    op.create_table(
        'semantic_review_findings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('guideline_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('flagged_excerpt', sa.Text(), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('uncertainty_reason', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['guideline_id'], ['policy_guidelines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['run_id'], ['semantic_review_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_semantic_review_findings_run_id'), 'semantic_review_findings', ['run_id'], unique=False)
    op.create_index(op.f('ix_semantic_review_findings_guideline_id'), 'semantic_review_findings', ['guideline_id'], unique=False)
    op.create_index(op.f('ix_semantic_review_findings_category'), 'semantic_review_findings', ['category'], unique=False)
    op.create_index(op.f('ix_semantic_review_findings_outcome'), 'semantic_review_findings', ['outcome'], unique=False)


def downgrade() -> None:
    # 3. Drop semantic_review_findings
    op.drop_index(op.f('ix_semantic_review_findings_outcome'), table_name='semantic_review_findings')
    op.drop_index(op.f('ix_semantic_review_findings_category'), table_name='semantic_review_findings')
    op.drop_index(op.f('ix_semantic_review_findings_guideline_id'), table_name='semantic_review_findings')
    op.drop_index(op.f('ix_semantic_review_findings_run_id'), table_name='semantic_review_findings')
    op.drop_table('semantic_review_findings')

    # 2. Drop semantic_review_runs
    op.drop_index(op.f('ix_semantic_review_runs_overall_outcome'), table_name='semantic_review_runs')
    op.drop_index(op.f('ix_semantic_review_runs_policy_id'), table_name='semantic_review_runs')
    op.drop_index(op.f('ix_semantic_review_runs_revision_id'), table_name='semantic_review_runs')
    op.drop_index(op.f('ix_semantic_review_runs_workspace_id'), table_name='semantic_review_runs')
    op.drop_table('semantic_review_runs')

    # 1. Drop columns from content_claims
    with op.batch_alter_table('content_claims') as batch_op:
        batch_op.drop_index(batch_op.f('ix_content_claims_discovery_status'))
        batch_op.drop_column('reviewed_at')
        batch_op.drop_column('reviewed_by_id')
        batch_op.drop_column('extraction_version')
        batch_op.drop_column('extraction_method')
        batch_op.drop_column('discovery_status')
