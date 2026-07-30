"""subscriptions extra columns + dev mode settings

Revision ID: b7e2f4a91c30
Revises: a1d94c6e77b2
Create Date: 2026-07-25 10:00:00.000000

CORRECTED: the `subscriptions` table already exists from the initial schema
(ee4e5b7811bd), so this migration ADDS the slice-12 columns to it rather than
creating the table. It also adds the dev-mode columns to user_settings.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e2f4a91c30'
down_revision = 'a1d94c6e77b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # subscriptions already exists (user_id PK, tier, status, stripe_customer_id,
    # current_period_end, canceled_at). Add only what slice 12 introduces.
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_subscription_id',
                                      sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('price_interval',
                                      sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('cancel_at_period_end', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))

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
        batch_op.drop_column('cancel_at_period_end')
        batch_op.drop_column('price_interval')
        batch_op.drop_column('stripe_subscription_id')
