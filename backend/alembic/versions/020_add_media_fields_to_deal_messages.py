"""add media fields to deal_messages

Revision ID: 020
Revises: 019
Create Date: 2026-02-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deal_messages",
        sa.Column("media_url", sa.String(1024), nullable=True),
    )
    op.add_column(
        "deal_messages",
        sa.Column("media_type", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deal_messages", "media_type")
    op.drop_column("deal_messages", "media_url")
