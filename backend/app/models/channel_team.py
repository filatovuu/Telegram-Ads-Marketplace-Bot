from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChannelTeamMember(Base):
    __tablename__ = "channel_team_members"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_user"),
    )

    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(50), default="manager", server_default="manager"
    )
    can_accept_deals: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    can_post: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    can_payout: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Relationships
    channel = relationship("Channel", back_populates="team_members")
    user = relationship("User", lazy="selectin")
