import json
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


def predict_probability(booking: dict) -> float:
    row = pd.DataFrame([{col: booking[col] for col in FEATURE_ORDER}])
    return float(pipeline.predict_proba(row)[0, 1])


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
