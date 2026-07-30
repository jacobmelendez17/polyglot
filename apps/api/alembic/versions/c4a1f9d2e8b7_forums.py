"""forums: categories, threads, replies, reports

Revision ID: c4a1f9d2e8b7
Revises: b7e2f4a91c30
Create Date: 2026-07-26 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'c4a1f9d2e8b7'
down_revision = 'b7e2f4a91c30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'forum_categories',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('slug', sa.String(length=60), nullable=False),
        sa.Column('title', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_forum_category_slug'),
    )
    with op.batch_alter_table('forum_categories', schema=None) as b:
        b.create_index(b.f('ix_forum_categories_slug'), ['slug'], unique=True)

    op.create_table(
        'forum_threads',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('category_id', app.db.base.GUID(), nullable=False),
        sa.Column('author_id', app.db.base.GUID(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('report_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('hidden_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hidden_by', app.db.base.GUID(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['forum_categories.id'], ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['hidden_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('forum_threads', schema=None) as b:
        b.create_index(b.f('ix_forum_threads_category_id'), ['category_id'], unique=False)
        b.create_index(b.f('ix_forum_threads_author_id'), ['author_id'], unique=False)

    op.create_table(
        'forum_replies',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('thread_id', app.db.base.GUID(), nullable=False),
        sa.Column('author_id', app.db.base.GUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('report_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hidden_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('hidden_by', app.db.base.GUID(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['forum_threads.id'], ),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['hidden_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('forum_replies', schema=None) as b:
        b.create_index(b.f('ix_forum_replies_thread_id'), ['thread_id'], unique=False)
        b.create_index(b.f('ix_forum_replies_author_id'), ['author_id'], unique=False)

    op.create_table(
        'forum_reports',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('reporter_id', app.db.base.GUID(), nullable=False),
        sa.Column('target_type', sa.String(length=10), nullable=False),
        sa.Column('target_id', app.db.base.GUID(), nullable=False),
        sa.Column('reason', sa.String(length=20), nullable=False, server_default='other'),
        sa.Column('detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', app.db.base.GUID(), nullable=True),
        sa.Column('action_taken', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reporter_id', 'target_type', 'target_id',
                           name='uq_forum_report_once'),
    )
    with op.batch_alter_table('forum_reports', schema=None) as b:
        b.create_index(b.f('ix_forum_reports_reporter_id'), ['reporter_id'], unique=False)
        b.create_index(b.f('ix_forum_reports_target_id'), ['target_id'], unique=False)


def downgrade() -> None:
    for table in ('forum_reports', 'forum_replies', 'forum_threads', 'forum_categories'):
        with op.batch_alter_table(table, schema=None) as b:
            for idx in list(_indexes.get(table, [])):
                b.drop_index(b.f(idx))
        op.drop_table(table)


_indexes = {
    'forum_categories': ['ix_forum_categories_slug'],
    'forum_threads': ['ix_forum_threads_category_id', 'ix_forum_threads_author_id'],
    'forum_replies': ['ix_forum_replies_thread_id', 'ix_forum_replies_author_id'],
    'forum_reports': ['ix_forum_reports_reporter_id', 'ix_forum_reports_target_id'],
}
