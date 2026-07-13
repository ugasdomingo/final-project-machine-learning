from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .ml import ALLOWED_CATEGORIES, CHANNEL_MAP

_CATEGORICAL_FIELDS = tuple(ALLOWED_CATEGORIES.keys())


class BookingInput(BaseModel):
    """Formato avanzado: las 26 features tal como las espera el modelo."""

    hotel: str
    meal: str
    market_segment: str
    distribution_channel: str
    reserved_room_type: str
    deposit_type: str
    customer_type: str
    arrival_date_month: str
    country: str
    lead_time: int = Field(ge=0)
    arrival_date_week_number: int = Field(ge=1, le=53)
    arrival_date_day_of_month: int = Field(ge=1, le=31)
    stays_in_weekend_nights: int = Field(ge=0)
    stays_in_week_nights: int = Field(ge=0)
    adults: int = Field(ge=0)
    children: float = Field(ge=0)
    babies: int = Field(ge=0)
    is_repeated_guest: int = Field(ge=0, le=1)
    previous_cancellations: int = Field(ge=0)
    previous_bookings_not_canceled: int = Field(ge=0)
    booking_changes: int = Field(ge=0)
    days_in_waiting_list: int = Field(ge=0)
    adr: float = Field(ge=0)
    required_car_parking_spaces: int = Field(ge=0)
    total_of_special_requests: int = Field(ge=0)
    has_company: bool = False

    @field_validator(*_CATEGORICAL_FIELDS)
    @classmethod
    def check_allowed_category(cls, v, info):
        allowed = ALLOWED_CATEGORIES.get(info.field_name)
        if allowed and v not in allowed:
            raise ValueError(f"{info.field_name} debe ser uno de: {allowed}")
        return v


class SimpleBookingInput(BaseModel):
    """
    Formato simple: lo que un recepcionista sabe de la reserva. El resto de
    features se derivan de las fechas o del perfil de la sede.
    """

    sede_id: int
    booking_date: date = Field(description="Fecha en que se hizo la reserva")
    checkin_date: date
    checkout_date: date
    adults: int = Field(ge=1)
    children: int = Field(default=0, ge=0)
    babies: int = Field(default=0, ge=0)
    channel: str = Field(description=f"Uno de: {list(CHANNEL_MAP)}")
    price_per_night: Optional[float] = Field(default=None, gt=0)
    room_type: Optional[str] = None
    country: Optional[str] = None
    meal: Optional[str] = None
    deposit_type: Optional[str] = None
    is_repeated_guest: bool = False
    previous_cancellations: int = Field(default=0, ge=0)
    special_requests: int = Field(default=0, ge=0)
    parking_spaces: int = Field(default=0, ge=0)

    @field_validator("channel")
    @classmethod
    def check_channel(cls, v):
        if v not in CHANNEL_MAP:
            raise ValueError(f"channel debe ser uno de: {list(CHANNEL_MAP)}")
        return v

    @field_validator("room_type")
    @classmethod
    def check_room_type(cls, v):
        if v is not None and v not in ALLOWED_CATEGORIES["reserved_room_type"]:
            raise ValueError(
                f"room_type debe ser uno de: {ALLOWED_CATEGORIES['reserved_room_type']}"
            )
        return v

    @field_validator("country")
    @classmethod
    def check_country(cls, v):
        if v is not None and v not in ALLOWED_CATEGORIES["country"]:
            raise ValueError("country debe ser un código ISO-3 presente en el modelo")
        return v

    @field_validator("meal")
    @classmethod
    def check_meal(cls, v):
        if v is not None and v not in ALLOWED_CATEGORIES["meal"]:
            raise ValueError(f"meal debe ser uno de: {ALLOWED_CATEGORIES['meal']}")
        return v

    @field_validator("deposit_type")
    @classmethod
    def check_deposit(cls, v):
        if v is not None and v not in ALLOWED_CATEGORIES["deposit_type"]:
            raise ValueError(
                f"deposit_type debe ser uno de: {ALLOWED_CATEGORIES['deposit_type']}"
            )
        return v

    @model_validator(mode="after")
    def check_dates(self):
        if self.checkout_date <= self.checkin_date:
            raise ValueError("checkout_date debe ser posterior a checkin_date")
        if self.booking_date > self.checkin_date:
            raise ValueError("booking_date no puede ser posterior a checkin_date")
        return self


class SedeCreate(BaseModel):
    name: str
    hotel_type: str = "City Hotel"
    total_rooms: int = Field(gt=0)
    default_country: str = "PRT"
    default_meal: str = "BB"
    default_deposit_type: str = "No Deposit"
    default_room_type: str = "A"
    default_adr: Optional[float] = Field(default=None, gt=0)

    @field_validator("hotel_type")
    @classmethod
    def check_hotel_type(cls, v):
        if v not in ALLOWED_CATEGORIES["hotel"]:
            raise ValueError(f"hotel_type debe ser uno de: {ALLOWED_CATEGORIES['hotel']}")
        return v

    @field_validator("default_country")
    @classmethod
    def check_country(cls, v):
        if v not in ALLOWED_CATEGORIES["country"]:
            raise ValueError("default_country debe ser un código ISO-3 presente en el modelo")
        return v


class SedeOut(BaseModel):
    id: int
    name: str
    hotel_type: str
    total_rooms: int
    default_country: str
    default_meal: str
    default_deposit_type: str
    default_room_type: str
    default_adr: Optional[float]

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    name: str
    email: Optional[str] = None
    sede: SedeCreate


class AccountOut(BaseModel):
    id: int
    name: str
    api_key: str
    sedes: List[SedeOut]

    class Config:
        from_attributes = True


class AdvancedPredictionRequest(BaseModel):
    sede_id: int
    arrival_date: Optional[date] = None
    booking: BookingInput


class PredictionResponse(BaseModel):
    cancellation_probability: float
    risk_level: str
    message: str


class PredictionHistoryItem(BaseModel):
    id: int
    sede_id: int
    sede_name: str
    arrival_date: Optional[date]
    probability: float
    risk_level: Optional[str]
    created_at: datetime


class OverbookingRequest(BaseModel):
    sede_id: int
    target_date: date
    risk_alpha: float = Field(default=0.05, gt=0, lt=1)
    bookings: List[BookingInput] = Field(min_length=1)


class OverbookingFromHistoryRequest(BaseModel):
    sede_id: int
    target_date: date
    risk_alpha: float = Field(default=0.05, gt=0, lt=1)


class OverbookingResponse(BaseModel):
    sede_name: str
    target_date: date
    n_bookings: int
    expected_cancellations: float
    std_cancellations: float
    recommended_extra_bookings: int
    recommended_overbooking_pct: float
    message: str


class OverbookingHistoryItem(BaseModel):
    id: int
    sede_id: int
    sede_name: str
    target_date: date
    n_bookings: int
    risk_alpha: float
    expected_cancellations: float
    recommended_extra: int
    recommended_pct: float
    created_at: datetime
