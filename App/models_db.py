from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class Account(Base):
    """Empresa u organización dueña de una o más sedes (hoteles, posadas...)."""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    # Solo se guarda el hash SHA-256; la key en claro se muestra una única
    # vez al registrarse.
    api_key_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=_now)

    sedes = relationship("Sede", back_populates="account")


class Sede(Base):
    """Una propiedad concreta: hotel, posada o sede de la empresa."""

    __tablename__ = "sedes"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    hotel_type = Column(String, nullable=False, default="City Hotel")
    total_rooms = Column(Integer, nullable=False)

    # Perfil: valores por defecto que rellenan la predicción simple.
    default_country = Column(String, nullable=False, default="PRT")
    default_meal = Column(String, nullable=False, default="BB")
    default_adr = Column(Float, nullable=True)

    created_at = Column(DateTime, default=_now)

    account = relationship("Account", back_populates="sedes")
    predictions = relationship("PredictionRecord", back_populates="sede")
    overbooking_calcs = relationship("OverbookingCalc", back_populates="sede")


class PredictionRecord(Base):
    __tablename__ = "predictions"
    # Cada reserva es única dentro de su sede: repetir el número actualiza la
    # predicción existente en vez de duplicarla.
    __table_args__ = (
        UniqueConstraint("sede_id", "booking_reference", name="uq_predictions_sede_reference"),
    )

    id = Column(Integer, primary_key=True)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=False, index=True)
    # Número/localizador de la reserva tal como lo maneja el hotel, para que el
    # historial sea reconocible y el hotel pueda ubicar los datos del huésped.
    booking_reference = Column(String, nullable=False)
    arrival_date = Column(Date, nullable=True, index=True)
    input_json = Column(Text, nullable=False)
    probability = Column(Float, nullable=False)
    risk_level = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)

    sede = relationship("Sede", back_populates="predictions")


class OverbookingCalc(Base):
    __tablename__ = "overbooking_calcs"

    id = Column(Integer, primary_key=True)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=False, index=True)
    target_date = Column(Date, nullable=False)
    n_bookings = Column(Integer, nullable=False)
    risk_alpha = Column(Float, nullable=False)
    expected_cancellations = Column(Float, nullable=False)
    recommended_extra = Column(Integer, nullable=False)
    recommended_pct = Column(Float, nullable=False)
    created_at = Column(DateTime, default=_now)

    sede = relationship("Sede", back_populates="overbooking_calcs")
