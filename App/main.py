import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import ml
from .auth import generate_api_key, get_account_sede, get_current_account, hash_api_key
from .countries import country_options
from .database import Base, engine, get_db
from .models_db import Account, OverbookingCalc, PredictionRecord, Sede
from .schemas import (
    AccountCreate,
    AccountOut,
    AdvancedPredictionRequest,
    OverbookingFromHistoryRequest,
    OverbookingHistoryItem,
    OverbookingRequest,
    OverbookingResponse,
    PredictionHistoryItem,
    PredictionResponse,
    SedeCreate,
    SedeOut,
    SimpleBookingInput,
)

BASE_DIR = Path(__file__).resolve().parent

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hotel Overbooking API",
    description=(
        "API que estima la probabilidad de cancelación de una reserva y calcula "
        "el % de overbooking recomendado por sede (hotel, posada o propiedad). "
        "Regístrate en `/accounts`, autentica con el header `X-API-Key` y usa "
        "`/predictions/simple` con los datos que cualquier recepcionista conoce."
    ),
    version="2.0.0",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "model": ml.METADATA["model_name"]}


# ---------------------------------------------------------------------------
# Cuentas y sedes
# ---------------------------------------------------------------------------

@app.post("/accounts", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    """Registra la empresa junto a su primera sede y devuelve la API key.
    La key solo se muestra en esta respuesta; en la base queda su hash."""
    api_key = generate_api_key()
    account = Account(
        name=payload.name, email=payload.email, api_key_hash=hash_api_key(api_key)
    )
    db.add(account)
    db.flush()
    db.add(Sede(account_id=account.id, **payload.sede.model_dump()))
    db.commit()
    db.refresh(account)
    return AccountOut(
        id=account.id,
        name=account.name,
        api_key=api_key,
        sedes=[SedeOut.model_validate(s) for s in account.sedes],
    )


@app.get("/sedes", response_model=list[SedeOut])
def list_sedes(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return db.query(Sede).filter(Sede.account_id == account.id).order_by(Sede.id).all()


@app.post("/sedes", response_model=SedeOut)
def create_sede(
    payload: SedeCreate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    sede = Sede(account_id=account.id, **payload.model_dump())
    db.add(sede)
    db.commit()
    db.refresh(sede)
    return sede


# ---------------------------------------------------------------------------
# Predicciones
# ---------------------------------------------------------------------------

def _save_prediction(db, sede, features, probability, arrival_date, booking_reference):
    level = ml.risk_level(probability)
    booking_reference = booking_reference.strip()

    # Cada reserva es única en su sede: si el número ya existe se actualiza la
    # predicción (la reserva pudo cambiar), en vez de duplicarla en el historial.
    record = (
        db.query(PredictionRecord)
        .filter(
            PredictionRecord.sede_id == sede.id,
            PredictionRecord.booking_reference == booking_reference,
        )
        .first()
    )
    updated = record is not None
    if record is None:
        record = PredictionRecord(sede_id=sede.id, booking_reference=booking_reference)
        db.add(record)
    record.arrival_date = arrival_date
    record.input_json = json.dumps(features, default=str)
    record.probability = probability
    record.risk_level = level
    db.commit()

    message = (
        f"Riesgo {level}: {probability * 100:.1f}% de probabilidad de que la "
        f"reserva {booking_reference} en '{sede.name}' se cancele."
    )
    if updated:
        message += " (Se actualizó la predicción anterior de esta reserva.)"
    return PredictionResponse(
        cancellation_probability=probability,
        risk_level=level,
        message=message,
    )


@app.post("/predictions/simple", response_model=PredictionResponse)
def create_simple_prediction(
    booking: SimpleBookingInput,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Predicción con los datos que cualquier recepcionista conoce; el resto
    se deriva de las fechas y del perfil de la sede."""
    sede = get_account_sede(booking.sede_id, account, db)
    features = ml.expand_simple_booking(booking.model_dump(), sede)
    probability = ml.predict_probability(features)
    return _save_prediction(
        db, sede, features, probability, booking.checkin_date, booking.booking_reference
    )


@app.post("/predictions", response_model=PredictionResponse)
def create_prediction(
    payload: AdvancedPredictionRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Predicción avanzada: las 23 features explícitas (para integraciones PMS)."""
    sede = get_account_sede(payload.sede_id, account, db)
    features = payload.booking.model_dump()
    probability = ml.predict_probability(features)
    return _save_prediction(
        db, sede, features, probability, payload.arrival_date, payload.booking_reference
    )


@app.get("/history/predictions", response_model=list[PredictionHistoryItem])
def list_predictions(
    limit: int = 20,
    sede_id: int | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PredictionRecord, Sede.name)
        .join(Sede, PredictionRecord.sede_id == Sede.id)
        .filter(Sede.account_id == account.id)
    )
    if sede_id is not None:
        query = query.filter(PredictionRecord.sede_id == sede_id)
    rows = query.order_by(PredictionRecord.created_at.desc()).limit(limit).all()
    return [
        PredictionHistoryItem(
            id=record.id,
            sede_id=record.sede_id,
            sede_name=sede_name,
            booking_reference=record.booking_reference,
            arrival_date=record.arrival_date,
            probability=record.probability,
            risk_level=record.risk_level,
            created_at=record.created_at,
        )
        for record, sede_name in rows
    ]


# ---------------------------------------------------------------------------
# Overbooking
# ---------------------------------------------------------------------------

def _save_overbooking(db, sede, target_date, risk_alpha, probabilities):
    result = ml.recommend_overbooking(
        probabilities, risk_alpha=risk_alpha, total_rooms=sede.total_rooms
    )
    db.add(
        OverbookingCalc(
            sede_id=sede.id,
            target_date=target_date,
            n_bookings=len(probabilities),
            risk_alpha=risk_alpha,
            expected_cancellations=result["expected_cancellations"],
            recommended_extra=result["recommended_extra_bookings"],
            recommended_pct=result.get("recommended_overbooking_pct", 0.0),
        )
    )
    db.commit()

    extra = result["recommended_extra_bookings"]
    pct = result.get("recommended_overbooking_pct", 0.0)
    return OverbookingResponse(
        sede_name=sede.name,
        target_date=target_date,
        n_bookings=len(probabilities),
        expected_cancellations=result["expected_cancellations"],
        std_cancellations=result["std_cancellations"],
        recommended_extra_bookings=extra,
        recommended_overbooking_pct=pct,
        message=(
            f"Para el {target_date} en '{sede.name}' se esperan "
            f"~{result['expected_cancellations']:.1f} cancelaciones entre "
            f"{len(probabilities)} reservas. Puedes aceptar {extra} reservas extra "
            f"({pct:.1f}% de tus {sede.total_rooms} habitaciones) con un "
            f"{risk_alpha * 100:.0f}% de riesgo de sobrevender."
        ),
    )


@app.post("/overbooking/from-predictions", response_model=OverbookingResponse)
def overbooking_from_predictions(
    payload: OverbookingFromHistoryRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Calcula el overbooking usando las predicciones ya guardadas cuya fecha
    de llegada coincide con la fecha objetivo. Sin pegar JSON."""
    sede = get_account_sede(payload.sede_id, account, db)
    records = (
        db.query(PredictionRecord)
        .filter(
            PredictionRecord.sede_id == sede.id,
            PredictionRecord.arrival_date == payload.target_date,
        )
        .all()
    )
    if not records:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay predicciones guardadas para '{sede.name}' con llegada "
                f"el {payload.target_date}. Registra primero las reservas de esa "
                "fecha en /predictions/simple."
            ),
        )
    probabilities = [r.probability for r in records]
    return _save_overbooking(db, sede, payload.target_date, payload.risk_alpha, probabilities)


@app.post("/overbooking", response_model=OverbookingResponse)
def create_overbooking(
    payload: OverbookingRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Cálculo por lote: recibe las reservas completas (para integraciones PMS)."""
    sede = get_account_sede(payload.sede_id, account, db)
    probabilities = [ml.predict_probability(b.model_dump()) for b in payload.bookings]
    return _save_overbooking(db, sede, payload.target_date, payload.risk_alpha, probabilities)


@app.get("/history/overbooking", response_model=list[OverbookingHistoryItem])
def list_overbooking(
    limit: int = 20,
    sede_id: int | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    query = (
        db.query(OverbookingCalc, Sede.name)
        .join(Sede, OverbookingCalc.sede_id == Sede.id)
        .filter(Sede.account_id == account.id)
    )
    if sede_id is not None:
        query = query.filter(OverbookingCalc.sede_id == sede_id)
    rows = query.order_by(OverbookingCalc.created_at.desc()).limit(limit).all()
    return [
        OverbookingHistoryItem(
            id=calc.id,
            sede_id=calc.sede_id,
            sede_name=sede_name,
            target_date=calc.target_date,
            n_bookings=calc.n_bookings,
            risk_alpha=calc.risk_alpha,
            expected_cancellations=calc.expected_cancellations,
            recommended_extra=calc.recommended_extra,
            recommended_pct=calc.recommended_pct,
            created_at=calc.created_at,
        )
        for calc, sede_name in rows
    ]


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.get("/")
def landing(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "hotel_types": ml.ALLOWED_CATEGORIES["hotel"],
            "countries": country_options(ml.ALLOWED_CATEGORIES["country"]),
            "meal_labels": ml.MEAL_LABELS,
        },
    )


@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "categorical_values": ml.ALLOWED_CATEGORIES,
            "countries": country_options(ml.ALLOWED_CATEGORIES["country"]),
            "channels": ml.CHANNEL_LABELS,
            "meal_labels": ml.MEAL_LABELS,
        },
    )
