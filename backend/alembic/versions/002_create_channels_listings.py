"""create channels, channel_team_members, listings tables

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- channels ---
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("invite_link", sa.String(length=512), nullable=True),
        sa.Column("subscribers", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("telegram_channel_id"),
    )
    op.create_index("ix_channels_telegram_channel_id", "channels", ["telegram_channel_id"])
    op.create_index("ix_channels_owner_id", "channels", ["owner_id"])

    # --- channel_team_members ---
    op.create_table(
        "channel_team_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="manager", nullable=False),
        sa.Column("can_accept_deals", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_post", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("can_payout", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_channel_user"),
    )
    op.create_index("ix_channel_team_members_channel_id", "channel_team_members", ["channel_id"])
    op.create_index("ix_channel_team_members_user_id", "channel_team_members", ["user_id"])

    # --- listings ---
    op.create_table(
        "listings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="TON", nullable=False),
        sa.Column("format", sa.String(length=50), server_default="post", nullable=False),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_listings_channel_id", "listings", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_listings_channel_id", table_name="listings")
    op.drop_table("listings")

    op.drop_index("ix_channel_team_members_user_id", table_name="channel_team_members")
    op.drop_index("ix_channel_team_members_channel_id", table_name="channel_team_members")
    op.drop_table("channel_team_members")

    op.drop_index("ix_channels_owner_id", table_name="channels")
    op.drop_index("ix_channels_telegram_channel_id", table_name="channels")
    op.drop_table("channels")
