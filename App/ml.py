import calendar
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm

MODEL_DIR = Path(__file__).resolve().parent.parent / "Model" / "models"

pipeline = joblib.load(MODEL_DIR / "model_pipeline.joblib")

with open(MODEL_DIR / "model_metadata.json", encoding="utf-8") as f:
    METADATA = json.load(f)

FEATURE_ORDER = METADATA["feature_order"]
ALLOWED_CATEGORIES = METADATA["categorical_values"]

# Una sola pregunta ("¿cómo llegó la reserva?") se traduce a las dos
# categorías que espera el modelo.
CHANNEL_MAP = {
    "directo": {"market_segment": "Direct", "distribution_channel": "Direct"},
    "ota": {"market_segment": "Online TA", "distribution_channel": "TA/TO"},
    "agencia": {"market_segment": "Offline TA/TO", "distribution_channel": "TA/TO"},
    "empresa": {"market_segment": "Corporate", "distribution_channel": "Corporate"},
    "grupo": {"market_segment": "Groups", "distribution_channel": "TA/TO"},
}

CHANNEL_LABELS = {
    "directo": "Web propia / teléfono / mostrador",
    "ota": "Portal online (Booking, Expedia...)",
    "agencia": "Agencia de viajes tradicional",
    "empresa": "Empresa / corporativo",
    "grupo": "Grupo / evento",
}

MEAL_LABELS = {
    "BB": "Solo desayuno (BB)",
    "HB": "Media pensión (HB)",
    "FB": "Pensión completa (FB)",
    "SC": "Sin comidas (SC)",
}

RISK_LEVELS = [(0.30, "bajo"), (0.60, "medio"), (1.01, "alto")]

# El dataset contiene patrones "perfectos" (p. ej. ninguna reserva con parking
# se canceló jamás) que llevan al modelo calibrado a devolver 0% o 100% exactos.
# Una predicción nunca debe afirmar certeza absoluta, así que la probabilidad
# servida se acota a este rango.
PROB_FLOOR = 0.01
PROB_CEILING = 0.99


def risk_level(probability: float) -> str:
    for threshold, label in RISK_LEVELS:
        if probability < threshold:
            return label
    return "alto"


def expand_simple_booking(simple: dict, sede) -> dict:
    """
    Convierte los campos que un recepcionista conoce (fechas, huéspedes, canal)
    en las 23 features que espera el pipeline v2, usando el perfil de la sede
    para los valores no informados.
    """
    checkin: date = simple["checkin_date"]
    checkout: date = simple["checkout_date"]
    booking_date: date = simple["booking_date"]

    weekend_nights = 0
    week_nights = 0
    night = checkin
    while night < checkout:
        if night.weekday() in (5, 6):  # noches de sábado y domingo
            weekend_nights += 1
        else:
            week_nights += 1
        night += timedelta(days=1)

    channel = CHANNEL_MAP[simple["channel"]]
    repeated = bool(simple.get("is_repeated_guest", False))

    return {
        "hotel": sede.hotel_type,
        "meal": simple.get("meal") or sede.default_meal,
        "market_segment": channel["market_segment"],
        "distribution_channel": channel["distribution_channel"],
        "customer_type": "Group" if simple["channel"] == "grupo" else "Transient",
        "arrival_date_month": calendar.month_name[checkin.month],
        "country": simple.get("country") or sede.default_country,
        "lead_time": max(0, (checkin - booking_date).days),
        "arrival_date_week_number": checkin.isocalendar()[1],
        "arrival_date_day_of_month": checkin.day,
        "stays_in_weekend_nights": weekend_nights,
        "stays_in_week_nights": week_nights,
        "adults": simple["adults"],
        "children": float(simple.get("children", 0)),
        "babies": simple.get("babies", 0),
        "is_repeated_guest": 1 if repeated else 0,
        "previous_cancellations": simple.get("previous_cancellations", 0),
        "previous_bookings_not_canceled": 1 if repeated else 0,
        "booking_changes": 0,
        "adr": simple.get("price_per_night") or sede.default_adr or 100.0,
        "required_car_parking_spaces": simple.get("parking_spaces", 0),
        "total_of_special_requests": simple.get("special_requests", 0),
        "has_company": simple["channel"] == "empresa",
    }


def predict_probability(booking: dict) -> float:
    row = pd.DataFrame([{col: booking[col] for col in FEATURE_ORDER}])
    probability = float(pipeline.predict_proba(row)[0, 1])
    return min(max(probability, PROB_FLOOR), PROB_CEILING)


def recommend_overbooking(probs, risk_alpha: float = 0.05, total_rooms: Optional[int] = None) -> dict:
    """
    Aproximación normal a la Poisson-binomial (ver Model/src/explore.ipynb, sección
    "Cálculo del overbooking" para la derivación y validación por Monte Carlo).
    """
    probs = np.asarray(probs, dtype=float)
    mu = probs.sum()
    sigma = np.sqrt((probs * (1 - probs)).sum())
    z = norm.ppf(1 - risk_alpha)

    extra_bookings = max(0, int(np.floor(mu - z * sigma)))

    result = {
        "expected_cancellations": round(float(mu), 2),
        "std_cancellations": round(float(sigma), 2),
        "recommended_extra_bookings": extra_bookings,
    }
    if total_rooms:
        result["recommended_overbooking_pct"] = round(100 * extra_bookings / total_rooms, 2)
    return result
