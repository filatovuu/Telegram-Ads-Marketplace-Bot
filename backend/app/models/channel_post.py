from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    __table_args__ = (
        Index("ix_channel_posts_channel_date", "channel_id", "date"),
        Index(
            "uq_channel_posts_channel_msg",
            "channel_id",
            "telegram_message_id",
            unique=True,
        ),
    )

    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    post_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="text", server_default="text"
    )
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    has_media: Mapped[bool] = mapped_column(default=False, server_default="false")
    reactions_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forward_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    channel = relationship("Channel", back_populates="posts")
    view_snapshots = relationship(
        "PostViewSnapshot", back_populates="post", cascade="all, delete-orphan"
    )
