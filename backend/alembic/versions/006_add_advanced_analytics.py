"""add post_view_snapshots, reactions/forwards to posts, advanced stats fields

Revision ID: 006
Revises: 005
Create Date: 2025-01-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- post_view_snapshots table ---
    op.create_table(
        "post_view_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("channel_posts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_post_view_snapshots_post_recorded",
        "post_view_snapshots",
        ["post_id", "recorded_at"],
    )

    # --- new columns on channel_posts ---
    op.add_column("channel_posts", sa.Column("reactions_count", sa.Integer(), nullable=True))
    op.add_column("channel_posts", sa.Column("forward_count", sa.Integer(), nullable=True))

    # --- new columns on channel_stats_snapshots ---
    op.add_column("channel_stats_snapshots", sa.Column("reactions_per_views", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("forwards_per_views", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("velocity_1h_ratio", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("posts_7d", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("posts_30d", sa.Integer(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("posts_per_day_7d", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("posts_per_day_30d", sa.Float(), nullable=True))
    op.add_column("channel_stats_snapshots", sa.Column("edit_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("channel_stats_snapshots", "edit_rate")
    op.drop_column("channel_stats_snapshots", "posts_per_day_30d")
    op.drop_column("channel_stats_snapshots", "posts_per_day_7d")
    op.drop_column("channel_stats_snapshots", "posts_30d")
    op.drop_column("channel_stats_snapshots", "posts_7d")
    op.drop_column("channel_stats_snapshots", "velocity_1h_ratio")
    op.drop_column("channel_stats_snapshots", "forwards_per_views")
    op.drop_column("channel_stats_snapshots", "reactions_per_views")
    op.drop_column("channel_posts", "forward_count")
    op.drop_column("channel_posts", "reactions_count")
    op.drop_index("ix_post_view_snapshots_post_recorded", table_name="post_view_snapshots")
    op.drop_table("post_view_snapshots")
