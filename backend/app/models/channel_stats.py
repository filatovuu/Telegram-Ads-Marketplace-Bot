from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChannelStatsSnapshot(Base):
    __tablename__ = "channel_stats_snapshots"
    __table_args__ = (
        Index("ix_channel_stats_channel_created", "channel_id", "created_at"),
    )

    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscribers: Mapped[int] = mapped_column(Integer, nullable=False)

    # Computed growth fields
    subscribers_growth_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscribers_growth_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscribers_growth_pct_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    subscribers_growth_pct_30d: Mapped[float | None] = mapped_column(Float, nullable=True)

    # From getChat metadata
    has_visible_history: Mapped[bool | None] = mapped_column(nullable=True)
    has_aggressive_anti_spam: Mapped[bool | None] = mapped_column(nullable=True)

    # View-based metrics (computed from tracked posts)
    avg_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_views_10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_views_30: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_views_50: Mapped[int | None] = mapped_column(Integer, nullable=True)
    median_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    posts_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)
    posts_tracked: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Advanced metrics
    reactions_per_views: Mapped[float | None] = mapped_column(Float, nullable=True)
    forwards_per_views: Mapped[float | None] = mapped_column(Float, nullable=True)
    velocity_1h_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    posts_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posts_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posts_per_day_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    posts_per_day_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    edit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Reserved for future expansion
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    premium_subscribers_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="bot_api", server_default="bot_api")

    # Relationships
    channel = relationship("Channel", back_populates="stats_snapshots")
