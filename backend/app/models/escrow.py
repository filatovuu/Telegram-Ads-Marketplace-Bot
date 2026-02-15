from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Escrow(Base):
    __tablename__ = "escrows"

    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    contract_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    advertiser_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 9), nullable=False, default=0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    on_chain_state: Mapped[str] = mapped_column(
        String(20), default="init", server_default="init", nullable=False
    )  # init / funded / release_sent / released / refund_sent / refunded
    deploy_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deposit_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    release_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    refund_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fee_percent: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
