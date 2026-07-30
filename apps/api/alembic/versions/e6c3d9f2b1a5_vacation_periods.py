"""vacation periods

Revision ID: e6c3d9f2b1a5
Revises: d5b2c8e1a9f4
Create Date: 2026-07-28 10:00:00.000000

A single new table. Nothing about existing scheduling changes until a user
actually pauses, so this migration is purely additive and trivially reversible.
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'e6c3d9f2b1a5'
down_revision = 'd5b2c8e1a9f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vacation_periods',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('shift_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_shifted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vacation_periods_user_id', 'vacation_periods',
                    ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_vacation_periods_user_id', table_name='vacation_periods')
    op.drop_table('vacation_periods')
