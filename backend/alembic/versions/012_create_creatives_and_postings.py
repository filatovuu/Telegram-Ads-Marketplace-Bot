"""create creative_versions and deal_postings tables, add retention_hours to deals

Revision ID: 012
Revises: 011
Create Date: 2025-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add retention_hours to deals
    op.add_column(
        "deals",
        sa.Column("retention_hours", sa.Integer(), nullable=False, server_default="24"),
    )

    # Create creative_versions table
    op.create_table(
        "creative_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("entities_json", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(1024), nullable=True),
        sa.Column("media_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="submitted"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_creative_versions_deal_id", "creative_versions", ["deal_id"])

    # Create deal_postings table
    op.create_table(
        "deal_postings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retained", sa.Boolean(), nullable=True),
        sa.Column("verification_error", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deal_postings_deal_id", "deal_postings", ["deal_id"], unique=True)
    op.create_index("ix_deal_postings_channel_id", "deal_postings", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_deal_postings_channel_id", table_name="deal_postings")
    op.drop_index("ix_deal_postings_deal_id", table_name="deal_postings")
    op.drop_table("deal_postings")
    op.drop_index("ix_creative_versions_deal_id", table_name="creative_versions")
    op.drop_table("creative_versions")
    op.drop_column("deals", "retention_hours")
