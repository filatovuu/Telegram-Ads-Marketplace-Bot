from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DealMessage(Base):
    __tablename__ = "deal_messages"

    deal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(20), default="text", server_default="text"
    )
    media_items: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    deal = relationship("Deal", backref="messages", lazy="selectin")
    sender = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_deal_messages_deal_created", "deal_id", "created_at"),
    )
