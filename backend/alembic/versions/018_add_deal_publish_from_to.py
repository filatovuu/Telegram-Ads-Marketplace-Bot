"""add deal publish_from, publish_to

Revision ID: 018
Revises: 017
Create Date: 2026-02-13 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("publish_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "deals",
        sa.Column("publish_to", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deals", "publish_to")
    op.drop_column("deals", "publish_from")
