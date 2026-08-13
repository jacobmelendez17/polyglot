"""custom_decks table (slice 43)

Revision ID: b53c9f10a7d4
Revises: a39e17b0c4d2
Create Date: 2026-08-12 00:00:00.000000

Learner-built decks: a name/description plus a JSON list of item refs.
"""
from alembic import op
import sqlalchemy as sa

from app.db.base import GUID

revision = 'b53c9f10a7d4'
down_revision = 'a39e17b0c4d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_decks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("item_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_custom_decks_user_id", "custom_decks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_custom_decks_user_id", table_name="custom_decks")
    op.drop_table("custom_decks")
