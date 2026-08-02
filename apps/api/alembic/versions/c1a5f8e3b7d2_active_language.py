"""active language

Revision ID: c1a5f8e3b7d2
Revises: b9d4e2f1a3c5
Create Date: 2026-08-01 12:00:00.000000

Makes the multilingual-ready schema usable at runtime: `languages.enabled` marks
which languages a learner may choose, and `profiles.active_language_code` records
which one they're currently learning. Both purely additive; existing rows default
to enabled / es-MX so nothing changes for current users.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1a5f8e3b7d2'
down_revision = 'b9d4e2f1a3c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('languages', schema=None) as b:
        b.add_column(sa.Column('enabled', sa.Boolean(), nullable=False,
                               server_default=sa.true()))
    with op.batch_alter_table('profiles', schema=None) as b:
        b.add_column(sa.Column('active_language_code', sa.String(length=10),
                               nullable=False, server_default='es-MX'))


def downgrade() -> None:
    with op.batch_alter_table('profiles', schema=None) as b:
        b.drop_column('active_language_code')
    with op.batch_alter_table('languages', schema=None) as b:
        b.drop_column('enabled')
