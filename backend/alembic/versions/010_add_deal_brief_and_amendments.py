"""add deal brief fields and deal_amendments table

Revision ID: 010
Revises: 009
Create Date: 2025-01-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add brief fields to deals
    op.add_column("deals", sa.Column("brief", sa.Text(), nullable=True))
    op.add_column(
        "deals",
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("deals", sa.Column("description", sa.Text(), nullable=True))

    # Create deal_amendments table
    op.create_table(
        "deal_amendments",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proposed_price", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "proposed_publish_date", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("proposed_description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="pending",
            nullable=False,
        ),
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
    )
    op.create_index(
        "ix_deal_amendments_deal_id",
        "deal_amendments",
        ["deal_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_deal_amendments_deal_id", table_name="deal_amendments")
    op.drop_table("deal_amendments")
    op.drop_column("deals", "description")
    op.drop_column("deals", "publish_date")
    op.drop_column("deals", "brief")
