from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    advertiser_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    budget_min: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    budget_max: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    publish_from: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_to: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    links: Mapped[str | None] = mapped_column(Text, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )

    # Relationships
    advertiser = relationship("User", backref="campaigns", lazy="selectin")
