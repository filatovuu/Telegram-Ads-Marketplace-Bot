"""replace media_url + media_type with media_items JSON in creative_versions

Revision ID: 022
Revises: 021
Create Date: 2026-02-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "creative_versions",
        sa.Column("media_items", sa.JSON(), nullable=True),
    )
    op.execute(
        """
        UPDATE creative_versions
        SET media_items = json_build_array(
            json_build_object('file_id', media_url, 'type', media_type)
        )
        WHERE media_url IS NOT NULL AND media_type IS NOT NULL
        """
    )
    op.drop_column("creative_versions", "media_url")
    op.drop_column("creative_versions", "media_type")


def downgrade() -> None:
    op.add_column(
        "creative_versions",
        sa.Column("media_url", sa.String(1024), nullable=True),
    )
    op.add_column(
        "creative_versions",
        sa.Column("media_type", sa.String(20), nullable=True),
    )
    op.execute(
        """
        UPDATE creative_versions
        SET media_url = media_items->0->>'file_id',
            media_type = media_items->0->>'type'
        WHERE media_items IS NOT NULL
        """
    )
    op.drop_column("creative_versions", "media_items")
