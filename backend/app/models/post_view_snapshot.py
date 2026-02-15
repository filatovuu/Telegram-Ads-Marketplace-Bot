from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PostViewSnapshot(Base):
    __tablename__ = "post_view_snapshots"
    __table_args__ = (
        Index("ix_post_view_snapshots_post_recorded", "post_id", "recorded_at"),
    )

    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channel_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    views: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    post = relationship("ChannelPost", back_populates="view_snapshots")
