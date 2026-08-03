"""testing maps

Revision ID: d2b6e4f9a1c8
Revises: c1a5f8e3b7d2
Create Date: 2026-08-02 10:00:00.000000

Question bank + attempts for the testing maps (cefr/app/life). Purely additive.
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'd2b6e4f9a1c8'
down_revision = 'c1a5f8e3b7d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'test_questions',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('language_id', app.db.base.GUID(), nullable=False),
        sa.Column('map', sa.String(length=8), nullable=False),
        sa.Column('band', sa.String(length=40), nullable=False, server_default=''),
        sa.Column('app_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('caption', sa.Text(), nullable=False, server_default=''),
        sa.Column('stem', sa.Text(), nullable=False, server_default=''),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('correct_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('explanation', sa.Text(), nullable=False, server_default=''),
        sa.Column('audio_asset_id', app.db.base.GUID(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='draft'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_test_questions_language_id', 'test_questions', ['language_id'])
    op.create_index('ix_test_questions_map', 'test_questions', ['map'])

    op.create_table(
        'test_attempts',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('map', sa.String(length=8), nullable=False),
        sa.Column('band', sa.String(length=40), nullable=False, server_default=''),
        sa.Column('state', sa.String(length=12), nullable=False, server_default='active'),
        sa.Column('question_ids', sa.JSON(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_test_attempts_user_id', 'test_attempts', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_test_attempts_user_id', table_name='test_attempts')
    op.drop_table('test_attempts')
    op.drop_index('ix_test_questions_map', table_name='test_questions')
    op.drop_index('ix_test_questions_language_id', table_name='test_questions')
    op.drop_table('test_questions')
