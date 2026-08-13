"""user_item_notes table (slice 44)

Revision ID: c73f0a91b2e5
Revises: b53c9f10a7d4
Create Date: 2026-08-13 00:00:00.000000

Per-user, per-item free-text note (≤250 words, enforced in the service).
"""
from alembic import op
import sqlalchemy as sa

from app.db.base import GUID
from app.models.enums import ItemType

revision = 'c73f0a91b2e5'
down_revision = 'b53c9f10a7d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_item_notes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_type", sa.Enum(ItemType, name="item_type", create_type=False), nullable=False),
        sa.Column("item_id", GUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "item_type", "item_id", name="uq_user_item_note"),
    )
    op.create_index("ix_user_item_notes_user_id", "user_item_notes", ["user_id"])
    op.create_index("ix_user_item_notes_item_id", "user_item_notes", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_user_item_notes_item_id", table_name="user_item_notes")
    op.drop_index("ix_user_item_notes_user_id", table_name="user_item_notes")
    op.drop_table("user_item_notes")
