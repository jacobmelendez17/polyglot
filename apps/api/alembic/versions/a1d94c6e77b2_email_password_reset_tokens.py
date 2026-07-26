"""email + password reset tokens

Revision ID: a1d94c6e77b2
Revises: c3f81a7d2b64
Create Date: 2026-07-24 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import app.db.base  # custom GUID type used by columns


revision = 'a1d94c6e77b2'
down_revision = 'c3f81a7d2b64'
branch_labels = None
depends_on = None


def _token_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name=f'uq_{name}_hash'),
    )
    with op.batch_alter_table(name, schema=None) as batch_op:
        batch_op.create_index(batch_op.f(f'ix_{name}_user_id'),
                              ['user_id'], unique=False)
        batch_op.create_index(batch_op.f(f'ix_{name}_token_hash'),
                              ['token_hash'], unique=True)


def _drop_token_table(name: str) -> None:
    with op.batch_alter_table(name, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(f'ix_{name}_token_hash'))
        batch_op.drop_index(batch_op.f(f'ix_{name}_user_id'))
    op.drop_table(name)


def upgrade() -> None:
    _token_table('password_reset_tokens')
    _token_table('email_verification_tokens')


def downgrade() -> None:
    _drop_token_table('email_verification_tokens')
    _drop_token_table('password_reset_tokens')
