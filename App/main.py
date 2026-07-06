import json
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import ml
from .auth import get_current_hotel
from .database import Base, engine, get_db
from .models_db import Hotel, OverbookingCalc, PredictionRecord
from .schemas import (
    BookingInput,
    HotelCreate,
    HotelOut,
    OverbookingHistoryItem,
    OverbookingRequest,
    OverbookingResponse,
    PredictionHistoryItem,
    PredictionResponse,
)

BASE_DIR = Path(__file__).resolve().parent

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hotel Overbooking API",
    description=(
        "API que estima la probabilidad de cancelación de una reserva y calcula "
        "el % de overbooking recomendado para que un hotel no se quede con "
        "habitaciones vacías."
    ),
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "model": ml.METADATA["model_name"]}


@app.post("/hotels", response_model=HotelOut)
def create_hotel(payload: HotelCreate, db: Session = Depends(get_db)):
    hotel = Hotel(name=payload.name, email=payload.email, total_rooms=payload.total_rooms)
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel


@app.post("/predictions", response_model=PredictionResponse)
def create_prediction(
    booking: BookingInput,
    hotel: Hotel = Depends(get_current_hotel),
    db: Session = Depends(get_db),
):
    probability = ml.predict_probability(booking.model_dump())

    record = PredictionRecord(
        hotel_id=hotel.id,
        input_json=json.dumps(booking.model_dump()),
        probability=probability,
    )
    db.add(record)
    db.commit()

    return PredictionResponse(cancellation_probability=probability)


@app.get("/history/predictions", response_model=list[PredictionHistoryItem])
def list_predictions(
    limit: int = 20,
    hotel: Hotel = Depends(get_current_hotel),
    db: Session = Depends(get_db),
):
    return (
        db.query(PredictionRecord)
        .filter(PredictionRecord.hotel_id == hotel.id)
        .order_by(PredictionRecord.created_at.desc())
        .limit(limit)
        .all()
    )


@app.post("/overbooking", response_model=OverbookingResponse)
def create_overbooking(
    payload: OverbookingRequest,
    hotel: Hotel = Depends(get_current_hotel),
    db: Session = Depends(get_db),
):
    probabilities = [ml.predict_probability(b.model_dump()) for b in payload.bookings]
    result = ml.recommend_overbooking(
        probabilities, risk_alpha=payload.risk_alpha, total_rooms=hotel.total_rooms
    )

    record = OverbookingCalc(
        hotel_id=hotel.id,
        target_date=payload.target_date,
        n_bookings=len(payload.bookings),
        risk_alpha=payload.risk_alpha,
        expected_cancellations=result["expected_cancellations"],
        recommended_extra=result["recommended_extra_bookings"],
        recommended_pct=result.get("recommended_overbooking_pct", 0.0),
    )
    db.add(record)
    db.commit()

    return OverbookingResponse(
        n_bookings=len(payload.bookings),
        expected_cancellations=result["expected_cancellations"],
        std_cancellations=result["std_cancellations"],
        recommended_extra_bookings=result["recommended_extra_bookings"],
        recommended_overbooking_pct=result.get("recommended_overbooking_pct", 0.0),
    )


@app.get("/history/overbooking", response_model=list[OverbookingHistoryItem])
def list_overbooking(
    limit: int = 20,
    hotel: Hotel = Depends(get_current_hotel),
    db: Session = Depends(get_db),
):
    return (
        db.query(OverbookingCalc)
        .filter(OverbookingCalc.hotel_id == hotel.id)
        .order_by(OverbookingCalc.created_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/")
def landing(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"categorical_values": ml.ALLOWED_CATEGORIES},
    )
