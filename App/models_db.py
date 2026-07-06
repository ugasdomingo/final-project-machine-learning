import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    api_key = Column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)
    total_rooms = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_now)

    predictions = relationship("PredictionRecord", back_populates="hotel")
    overbooking_calcs = relationship("OverbookingCalc", back_populates="hotel")


class PredictionRecord(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    input_json = Column(Text, nullable=False)
    probability = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_now)

    hotel = relationship("Hotel", back_populates="predictions")


class OverbookingCalc(Base):
    __tablename__ = "overbooking_calcs"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    target_date = Column(String, nullable=False)
    n_bookings = Column(Integer, nullable=False)
    risk_alpha = Column(Float, nullable=False)
    expected_cancellations = Column(Float, nullable=False)
    recommended_extra = Column(Integer, nullable=False)
    recommended_pct = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_now)

    hotel = relationship("Hotel", back_populates="overbooking_calcs")
