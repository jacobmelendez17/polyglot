"""guided tour state

Revision ID: c3f81a7d2b64
Revises: 70e897feb3f0
Create Date: 2026-07-23 20:10:00.000000
"""
from alembic import op
import sqlalchemy as sa
import app.db.base  # custom GUID type used by columns


revision = 'c3f81a7d2b64'
down_revision = '70e897feb3f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_tour_state',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('tour_key', sa.String(length=40), nullable=False),
        sa.Column('step_index', sa.SmallInteger(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('skipped', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tour_key', name='uq_user_tour'),
    )
    with op.batch_alter_table('user_tour_state', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_user_tour_state_user_id'), ['user_id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('user_tour_state', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_tour_state_user_id'))
    op.drop_table('user_tour_state')
