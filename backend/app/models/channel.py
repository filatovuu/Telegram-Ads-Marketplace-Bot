from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Channel(Base):
    __tablename__ = "channels"

    telegram_channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subscribers: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    avg_views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    language_manual: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    bot_is_admin: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    owner = relationship("User", backref="channels", lazy="selectin")
    team_members = relationship(
        "ChannelTeamMember", back_populates="channel", cascade="all, delete-orphan"
    )
    listings = relationship(
        "Listing", back_populates="channel", cascade="all, delete-orphan"
    )
    stats_snapshots = relationship(
        "ChannelStatsSnapshot", back_populates="channel", cascade="all, delete-orphan"
    )
    posts = relationship(
        "ChannelPost", back_populates="channel", cascade="all, delete-orphan"
    )
