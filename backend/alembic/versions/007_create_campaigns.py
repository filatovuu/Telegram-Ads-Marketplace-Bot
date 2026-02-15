"""create campaigns table

Revision ID: 007
Revises: 006
Create Date: 2025-01-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("advertiser_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("target_language", sa.String(10), nullable=True),
        sa.Column("budget_min", sa.Numeric(18, 6), nullable=False),
        sa.Column("budget_max", sa.Numeric(18, 6), nullable=False),
        sa.Column("publish_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("links", sa.Text(), nullable=True),
        sa.Column("restrictions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("campaigns")
