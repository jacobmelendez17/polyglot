"""feedback responses + onboarding backfill

Revision ID: d5b2c8e1a9f4
Revises: c4a1f9d2e8b7
Create Date: 2026-07-27 10:00:00.000000

Two changes:
  1. feedback_tickets gains an admin response (text + who + when), so "answered"
     means there's an actual reply, not just a flipped flag.
  2. Backfill profiles.onboarding_completed_at for existing users. Onboarding was
     previously remembered only in the browser; now the server column is the
     source of truth and a NULL means "hasn't onboarded". Existing users have
     effectively onboarded, so we stamp them — otherwise everyone would be sent
     back through the intro on their next sign-in.
"""
from alembic import op
import sqlalchemy as sa
import app.db.base


revision = 'd5b2c8e1a9f4'
down_revision = 'c4a1f9d2e8b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('feedback_tickets', schema=None) as b:
        b.add_column(sa.Column('admin_response', sa.Text(), nullable=False,
                               server_default=''))
        b.add_column(sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column('responded_by', app.db.base.GUID(), nullable=True))
        b.create_foreign_key('fk_feedback_responded_by', 'users',
                             ['responded_by'], ['id'])

    # Backfill: existing users are treated as already-onboarded so this change
    # doesn't resurface the intro for them. New signups start NULL and see it.
    op.execute(
        "UPDATE profiles SET onboarding_completed_at = now() "
        "WHERE onboarding_completed_at IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table('feedback_tickets', schema=None) as b:
        b.drop_constraint('fk_feedback_responded_by', type_='foreignkey')
        b.drop_column('responded_by')
        b.drop_column('responded_at')
        b.drop_column('admin_response')
    # The backfill is data-only and intentionally not reversed.
