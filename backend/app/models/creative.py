from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CreativeVersion(Base):
    __tablename__ = "creative_versions"

    deal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    entities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="submitted", server_default="submitted"
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    deal = relationship("Deal", backref="creative_versions", lazy="selectin")
