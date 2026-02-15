"""add deal owner_wallet_address

Revision ID: 019
Revises: 018
Create Date: 2026-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("owner_wallet_address", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deals", "owner_wallet_address")
