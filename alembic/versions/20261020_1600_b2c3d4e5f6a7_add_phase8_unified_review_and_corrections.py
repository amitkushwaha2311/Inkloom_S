"""add_phase8_unified_review_and_corrections

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-20 16:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update review_decisions with policy reference and review run ID
    with op.batch_alter_table('review_decisions') as batch_op:
        batch_op.add_column(sa.Column('policy_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('policy_version', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('review_run_id', sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f('ix_review_decisions_policy_id'), ['policy_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_review_decisions_review_run_id'), ['review_run_id'], unique=False)
        batch_op.create_foreign_key('fk_review_decisions_policy_id', 'brand_policies', ['policy_id'], ['id'], ondelete='SET NULL')

    # 2. Create correction_suggestions table
    op.create_table(
        'correction_suggestions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('submission_id', sa.Uuid(), nullable=False),
        sa.Column('revision_id', sa.Uuid(), nullable=False),
        sa.Column('finding_id', sa.Uuid(), nullable=True),
        sa.Column('guideline_id', sa.Uuid(), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('proposed_replacement', sa.Text(), nullable=True),
        sa.Column('recommended_action', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('evidence_source_id', sa.Uuid(), nullable=True),
        sa.Column('evidence_excerpt', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='proposed', nullable=False),
        sa.Column('created_by_id', sa.String(length=64), nullable=False),
        sa.Column('reviewed_by_id', sa.String(length=64), nullable=True),
        sa.Column('applied_revision_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['applied_revision_id'], ['content_revisions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['evidence_source_id'], ['evidence_sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['guideline_id'], ['policy_guidelines.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revision_id'], ['content_revisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submission_id'], ['content_submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['brand_workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_correction_suggestions_workspace_id'), 'correction_suggestions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_submission_id'), 'correction_suggestions', ['submission_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_revision_id'), 'correction_suggestions', ['revision_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_finding_id'), 'correction_suggestions', ['finding_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_guideline_id'), 'correction_suggestions', ['guideline_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_evidence_source_id'), 'correction_suggestions', ['evidence_source_id'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_status'), 'correction_suggestions', ['status'], unique=False)
    op.create_index(op.f('ix_correction_suggestions_applied_revision_id'), 'correction_suggestions', ['applied_revision_id'], unique=False)


def downgrade() -> None:
    # 2. Drop correction_suggestions
    op.drop_index(op.f('ix_correction_suggestions_applied_revision_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_status'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_evidence_source_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_guideline_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_finding_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_revision_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_submission_id'), table_name='correction_suggestions')
    op.drop_index(op.f('ix_correction_suggestions_workspace_id'), table_name='correction_suggestions')
    op.drop_table('correction_suggestions')

    # 1. Revert review_decisions columns
    with op.batch_alter_table('review_decisions') as batch_op:
        batch_op.drop_constraint('fk_review_decisions_policy_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_review_decisions_review_run_id'))
        batch_op.drop_index(batch_op.f('ix_review_decisions_policy_id'))
        batch_op.drop_column('review_run_id')
        batch_op.drop_column('policy_version')
        batch_op.drop_column('policy_id')
