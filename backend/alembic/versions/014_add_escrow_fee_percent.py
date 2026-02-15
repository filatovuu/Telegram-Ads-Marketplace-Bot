"""add fee_percent to escrows

Revision ID: 014
Revises: 013
Create Date: 2025-01-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "escrows",
        sa.Column("fee_percent", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("escrows", "fee_percent")
