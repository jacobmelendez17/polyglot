"""reading resource

Revision ID: b9d4e2f1a3c5
Revises: a8f3c1e9d2b4
Create Date: 2026-08-01 10:00:00.000000

Two new tables for the reading resource. Purely additive.
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'b9d4e2f1a3c5'
down_revision = 'a8f3c1e9d2b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reading_texts',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('language_id', app.db.base.GUID(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False, server_default=''),
        sa.Column('author', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('source_type', sa.String(length=12), nullable=False, server_default='original'),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('external_url', sa.String(length=600), nullable=False, server_default=''),
        sa.Column('summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='draft'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reading_texts_language_id', 'reading_texts',
                    ['language_id'], unique=False)

    op.create_table(
        'reading_annotations',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('text_id', app.db.base.GUID(), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False),
        sa.Column('end_offset', sa.Integer(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=False, server_default=''),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['text_id'], ['reading_texts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reading_annotations_user_id', 'reading_annotations',
                    ['user_id'], unique=False)
    op.create_index('ix_reading_annotations_text_id', 'reading_annotations',
                    ['text_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_reading_annotations_text_id', table_name='reading_annotations')
    op.drop_index('ix_reading_annotations_user_id', table_name='reading_annotations')
    op.drop_table('reading_annotations')
    op.drop_index('ix_reading_texts_language_id', table_name='reading_texts')
    op.drop_table('reading_texts')
