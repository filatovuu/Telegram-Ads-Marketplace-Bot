"""replace media_url + media_type with media_items JSON in deal_messages

Revision ID: 021
Revises: 020
Create Date: 2026-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deal_messages",
        sa.Column("media_items", sa.JSON(), nullable=True),
    )
    # Backfill: convert existing single-media rows to JSON array
    op.execute(
        """
        UPDATE deal_messages
        SET media_items = json_build_array(
            json_build_object('file_id', media_url, 'type', media_type)
        )
        WHERE media_url IS NOT NULL AND media_type IS NOT NULL
        """
    )
    op.drop_column("deal_messages", "media_url")
    op.drop_column("deal_messages", "media_type")


def downgrade() -> None:
    op.add_column(
        "deal_messages",
        sa.Column("media_url", sa.String(1024), nullable=True),
    )
    op.add_column(
        "deal_messages",
        sa.Column("media_type", sa.String(20), nullable=True),
    )
    # Backfill: extract first item from JSON array
    op.execute(
        """
        UPDATE deal_messages
        SET media_url = media_items->0->>'file_id',
            media_type = media_items->0->>'type'
        WHERE media_items IS NOT NULL
        """
    )
    op.drop_column("deal_messages", "media_items")
