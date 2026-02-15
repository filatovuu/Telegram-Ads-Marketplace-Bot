"""create escrows table and add wallet_address to users

Revision ID: 011
Revises: 010
Create Date: 2025-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add wallet_address to users
    op.add_column("users", sa.Column("wallet_address", sa.String(128), nullable=True))

    # Create escrows table
    op.create_table(
        "escrows",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("contract_address", sa.String(128), nullable=True),
        sa.Column("advertiser_address", sa.String(128), nullable=True),
        sa.Column("owner_address", sa.String(128), nullable=True),
        sa.Column("platform_address", sa.String(128), nullable=True),
        sa.Column("amount", sa.Numeric(18, 9), nullable=False, server_default="0"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "on_chain_state",
            sa.String(20),
            server_default="init",
            nullable=False,
        ),
        sa.Column("deploy_tx_hash", sa.String(128), nullable=True),
        sa.Column("deposit_tx_hash", sa.String(128), nullable=True),
        sa.Column("release_tx_hash", sa.String(128), nullable=True),
        sa.Column("refund_tx_hash", sa.String(128), nullable=True),
        sa.Column("funded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_escrows_deal_id", "escrows", ["deal_id"])
    op.create_index("ix_escrows_on_chain_state", "escrows", ["on_chain_state"])


def downgrade() -> None:
    op.drop_index("ix_escrows_on_chain_state", table_name="escrows")
    op.drop_index("ix_escrows_deal_id", table_name="escrows")
    op.drop_table("escrows")
    op.drop_column("users", "wallet_address")
