from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .ml import ALLOWED_CATEGORIES

_CATEGORICAL_FIELDS = tuple(ALLOWED_CATEGORIES.keys())


class BookingInput(BaseModel):
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


class PredictionResponse(BaseModel):
    cancellation_probability: float


class PredictionHistoryItem(BaseModel):
    id: int
    probability: float
    created_at: datetime

    class Config:
        from_attributes = True


class HotelCreate(BaseModel):
    name: str
    email: Optional[str] = None
    total_rooms: int = Field(gt=0)


class HotelOut(BaseModel):
    id: int
    name: str
    total_rooms: int
    api_key: str

    class Config:
        from_attributes = True


class OverbookingRequest(BaseModel):
    target_date: str
    risk_alpha: float = Field(default=0.05, gt=0, lt=1)
    bookings: List[BookingInput]


class OverbookingResponse(BaseModel):
    n_bookings: int
    expected_cancellations: float
    std_cancellations: float
    recommended_extra_bookings: int
    recommended_overbooking_pct: float


class OverbookingHistoryItem(BaseModel):
    id: int
    target_date: str
    n_bookings: int
    risk_alpha: float
    expected_cancellations: float
    recommended_extra: int
    recommended_pct: float
    created_at: datetime

    class Config:
        from_attributes = True
