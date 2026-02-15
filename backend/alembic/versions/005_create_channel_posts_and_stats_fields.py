"""create channel_posts table and add computed metric fields to snapshots

Revision ID: 005
Revises: 004
Create Date: 2025-01-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- channel_posts table ---
    op.create_table(
        "channel_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("post_type", sa.String(30), server_default="text", nullable=False),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("has_media", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("media_group_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_channel_posts_channel_date",
        "channel_posts",
        ["channel_id", "date"],
    )
    op.create_index(
        "uq_channel_posts_channel_msg",
        "channel_posts",
        ["channel_id", "telegram_message_id"],
        unique=True,
    )

    # --- new columns on channel_stats_snapshots ---
    op.add_column("channel_stats_snapshots", sa.Column("avg_views_10", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("avg_views_30", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("avg_views_50", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("median_views", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("reach_pct", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("posts_tracked", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("channel_stats_snapshots", "posts_tracked")
    op.drop_column("channel_stats_snapshots", "reach_pct")
    op.drop_column("channel_stats_snapshots", "median_views")
    op.drop_column("channel_stats_snapshots", "avg_views_50")
    op.drop_column("channel_stats_snapshots", "avg_views_30")
    op.drop_column("channel_stats_snapshots", "avg_views_10")
    op.drop_index("uq_channel_posts_channel_msg", table_name="channel_posts")
    op.drop_index("ix_channel_posts_channel_date", table_name="channel_posts")
    op.drop_table("channel_posts")
