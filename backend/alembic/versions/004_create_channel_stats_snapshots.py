"""create channel_stats_snapshots table

Revision ID: 004
Revises: 003
Create Date: 2025-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_stats_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscribers", sa.Integer(), nullable=False),
        sa.Column("subscribers_growth_7d", sa.Integer(), nullable=True),
        sa.Column("subscribers_growth_30d", sa.Integer(), nullable=True),
        sa.Column("subscribers_growth_pct_7d", sa.Float(), nullable=True),
        sa.Column("subscribers_growth_pct_30d", sa.Float(), nullable=True),
        sa.Column("has_visible_history", sa.Boolean(), nullable=True),
        sa.Column("has_aggressive_anti_spam", sa.Boolean(), nullable=True),
        sa.Column("avg_views", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("premium_subscribers_pct", sa.Float(), nullable=True),
        sa.Column("posts_per_week", sa.Float(), nullable=True),
        sa.Column("source", sa.String(50), server_default="bot_api", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_channel_stats_channel_created",
        "channel_stats_snapshots",
        ["channel_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_channel_stats_channel_created", table_name="channel_stats_snapshots")
    op.drop_table("channel_stats_snapshots")
