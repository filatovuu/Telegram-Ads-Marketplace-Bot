from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Deal(Base):
    __tablename__ = "deals"

    listing_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    advertiser_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="DRAFT", server_default="DRAFT"
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), default="TON", server_default="TON"
    )
    escrow_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_wallet_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    wallet_notification_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publish_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publish_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_hours: Mapped[int] = mapped_column(
        Integer, default=24, server_default="24"
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    listing = relationship("Listing", backref="deals", lazy="selectin")
    campaign = relationship("Campaign", backref="deals", lazy="selectin")
    advertiser = relationship("User", foreign_keys=[advertiser_id], lazy="selectin")
    owner = relationship("User", foreign_keys=[owner_id], lazy="selectin")
