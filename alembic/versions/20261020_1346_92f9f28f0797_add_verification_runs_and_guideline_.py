"""add_verification_runs_and_guideline_rule_config_phase5

Revision ID: 92f9f28f0797
Revises: 018fec480e93
Create Date: 2026-10-20 13:46:07.600999+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f9f28f0797'
down_revision: Union[str, None] = '018fec480e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('verification_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('revision_id', sa.Uuid(), nullable=False),
    sa.Column('policy_id', sa.Uuid(), nullable=False),
    sa.Column('policy_version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('total_rules', sa.Integer(), nullable=False),
    sa.Column('passed_rules', sa.Integer(), nullable=False),
    sa.Column('violation_count', sa.Integer(), nullable=False),
    sa.Column('inconclusive_count', sa.Integer(), nullable=False),
    sa.Column('executed_by_id', sa.String(length=64), nullable=False),
    sa.Column('execution_time_ms', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['policy_id'], ['brand_policies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['revision_id'], ['content_revisions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_runs_policy_id'), 'verification_runs', ['policy_id'], unique=False)
    op.create_index(op.f('ix_verification_runs_revision_id'), 'verification_runs', ['revision_id'], unique=False)

    with op.batch_alter_table('policy_guidelines') as batch_op:
        batch_op.add_column(sa.Column('rule_config', sa.JSON(), server_default=sa.text("'{}'"), nullable=False))

    with op.batch_alter_table('verification_findings') as batch_op:
        batch_op.add_column(sa.Column('run_id', sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f('ix_verification_findings_run_id'), ['run_id'], unique=False)
        batch_op.create_foreign_key('fk_verification_findings_run_id', 'verification_runs', ['run_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    with op.batch_alter_table('verification_findings') as batch_op:
        batch_op.drop_constraint('fk_verification_findings_run_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_verification_findings_run_id'))
        batch_op.drop_column('run_id')

    with op.batch_alter_table('policy_guidelines') as batch_op:
        batch_op.drop_column('rule_config')

    op.drop_index(op.f('ix_verification_runs_revision_id'), table_name='verification_runs')
    op.drop_index(op.f('ix_verification_runs_policy_id'), table_name='verification_runs')
    op.drop_table('verification_runs')
