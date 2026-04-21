import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_rating_user"),
        {"schema": "ranking_schema"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    primary_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    behavioral_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    combined_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    total_likes_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_skips_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_chats_initiated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", name="uq_referral_referred"),
        {"schema": "ranking_schema"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    referred_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RatingHistory(Base):
    __tablename__ = "rating_history"
    __table_args__ = {"schema": "ranking_schema"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    primary_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    behavioral_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    combined_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
