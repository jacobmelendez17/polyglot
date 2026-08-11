"""add batch column to vocabulary_items (slice 39)

Revision ID: a39e17b0c4d2
Revises: d2b6e4f9a1c8
Create Date: 2026-08-10 00:00:00.000000

Vocabulary items store their level via module_id but had no batch (which of the
4 themed vocab batches). The in-app editor needs to move items between batches,
so add a small integer batch (default 1). Purely additive and reversible.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a39e17b0c4d2'
down_revision = 'd2b6e4f9a1c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('vocabulary_items', schema=None) as b:
        b.add_column(sa.Column('batch', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    with op.batch_alter_table('vocabulary_items', schema=None) as b:
        b.drop_column('batch')
