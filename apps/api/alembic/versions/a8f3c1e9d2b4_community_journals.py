"""community journals

Revision ID: a8f3c1e9d2b4
Revises: f7d4a2c8e9b3
Create Date: 2026-07-31 10:00:00.000000

Adds sharing + moderation columns to journal_entries and the journal_feedback
table. `visibility` (already present, default 'private') stays the private/shared
flag; `shared_at` records when an entry was shared (feed ordering); `share_hidden`
lets a moderator remove a shared entry from the community feed without touching the
owner's own copy. Purely additive.
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'a8f3c1e9d2b4'
down_revision = 'e6c3d9f2b1a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('journal_entries', schema=None) as b:
        b.add_column(sa.Column('shared_at', sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column('share_hidden', sa.Boolean(), nullable=False,
                               server_default=sa.false()))
        b.add_column(sa.Column('share_hidden_reason', sa.Text(), nullable=True))

    op.create_table(
        'journal_feedback',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('entry_id', app.db.base.GUID(), nullable=False),
        sa.Column('author_id', app.db.base.GUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('hidden_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['journal_entries.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_journal_feedback_entry_id', 'journal_feedback',
                    ['entry_id'], unique=False)
    op.create_index('ix_journal_feedback_author_id', 'journal_feedback',
                    ['author_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_journal_feedback_author_id', table_name='journal_feedback')
    op.drop_index('ix_journal_feedback_entry_id', table_name='journal_feedback')
    op.drop_table('journal_feedback')
    with op.batch_alter_table('journal_entries', schema=None) as b:
        b.drop_column('share_hidden_reason')
        b.drop_column('share_hidden')
        b.drop_column('shared_at')
