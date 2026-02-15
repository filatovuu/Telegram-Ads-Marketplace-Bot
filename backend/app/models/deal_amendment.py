from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DealAmendment(Base):
    __tablename__ = "deal_amendments"

    deal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposed_by_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    proposed_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    proposed_publish_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    proposed_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )

    # Relationships
    deal = relationship("Deal", backref="amendments", lazy="selectin")
    proposed_by = relationship("User", lazy="selectin")
