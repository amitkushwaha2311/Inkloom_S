"""add_users_refresh_tokens_phase3

Revision ID: 018fec480e93
Revises: bcdbc3a36dcf
Create Date: 2026-10-20 13:09:57.521971+00:00

Note: The alter_column for audit_events.event_type is intentionally omitted.
SQLite stores non-native enums as VARCHAR, and the column width is already
sufficient for all enum values. Expanding enum vocabulary is validated at the
Python layer (native_enum=False) — no DDL change is required.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018fec480e93'
down_revision: Union[str, None] = 'bcdbc3a36dcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False,
              comment='True once the user has confirmed their email address'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False,
              comment='SHA-256 hex digest of the raw opaque token string'),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_revoked', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hint', sa.String(length=8), nullable=True),
    sa.Column('user_agent_snippet', sa.Text(), nullable=True),
    sa.Column('ip_address_hash', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    # audit_events.event_type: no DDL change needed (SQLite VARCHAR, validated in Python)


def downgrade() -> None:
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
