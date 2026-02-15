"""add performance indexes

Revision ID: 016
Revises: 015
Create Date: 2025-01-21 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS to be idempotent (safe against partial reruns)
    conn = op.get_bind()
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deals_status ON deals (status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deals_advertiser_status ON deals (advertiser_id, status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deals_owner_status ON deals (owner_id, status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_listings_active_channel ON listings (is_active, channel_id)"))
    # ix_escrows_on_chain_state already created in migration 011
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deal_postings_schedule ON deal_postings (scheduled_at, posted_at)"))


def downgrade() -> None:
    op.drop_index("ix_deal_postings_schedule", table_name="deal_postings")
    op.drop_index("ix_listings_active_channel", table_name="listings")
    op.drop_index("ix_deals_owner_status", table_name="deals")
    op.drop_index("ix_deals_advertiser_status", table_name="deals")
    op.drop_index("ix_deals_status", table_name="deals")
