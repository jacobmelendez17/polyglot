"""subscriptions + dev mode settings

Revision ID: b7e2f4a91c30
Revises: a1d94c6e77b2
Create Date: 2026-07-25 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
import app.db.base  # custom GUID type used by columns


revision = 'b7e2f4a91c30'
down_revision = 'a1d94c6e77b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', app.db.base.GUID(), nullable=False),
        sa.Column('user_id', app.db.base.GUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='free'),
        sa.Column('stripe_customer_id', sa.String(length=80), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=80), nullable=True),
        sa.Column('price_interval', sa.String(length=10), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_subscription_user'),
    )
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscriptions_user_id'),
                              ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_stripe_customer_id'),
                              ['stripe_customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_subscriptions_stripe_subscription_id'),
                              ['stripe_subscription_id'], unique=False)

    # Dev mode lives on user_settings: an admin-only switch plus the SRS scale.
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dev_mode', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.add_column(sa.Column('dev_srs_scale', sa.Float(), nullable=False,
                                      server_default='1.0'))


def downgrade() -> None:
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.drop_column('dev_srs_scale')
        batch_op.drop_column('dev_mode')

    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subscriptions_stripe_subscription_id'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_stripe_customer_id'))
        batch_op.drop_index(batch_op.f('ix_subscriptions_user_id'))
    op.drop_table('subscriptions')
