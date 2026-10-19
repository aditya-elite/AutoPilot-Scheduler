"""
Predictive Maintenance / Failure Risk Model
=============================================

Purpose: produce `machines.failure_risk_score` (0..1) so the AI
Control Center can surface "this machine is likely to break down
soon" ahead of time, and so the scheduler can be nudged (via the
`predicted_failure_risk` downtime reason) to lighten load on
high-risk machines before they actually fail.

Features (again kept simple/explainable for v1):
    - hours_since_last_maintenance
    - average_daily_utilization_pct   (heavier use -> more wear)
    - age_years
    - historical_breakdown_count      (past reliability)

Model: RandomForestClassifier predicting probability of a breakdown
within the next 7 days. Chosen over gradient boosting here because
factory reliability engineers tend to trust (and can sanity-check)
feature importances from random forests, and the classification
framing (probability of breakdown) maps directly onto the
`failure_risk_score` column the UI displays as a gauge/badge.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = Path(__file__).parent / "artifacts" / "failure_model.joblib"

FEATURE_COLUMNS = [
    "hours_since_last_maintenance",
    "average_daily_utilization_pct",
    "age_years",
    "historical_breakdown_count",
]


def generate_synthetic_training_data(n_samples: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    hours_since_maint = rng.uniform(0, 2000, size=n_samples)
    utilization = rng.uniform(20, 100, size=n_samples)
    age_years = rng.uniform(0, 15, size=n_samples)
    breakdown_count = rng.poisson(lam=1.5, size=n_samples)

    # Latent risk score combining the factors, then thresholded with
    # noise into a binary "broke down within 7 days" label.
    risk_signal = (
        0.0025 * hours_since_maint
        + 0.02 * utilization
        + 0.08 * age_years
        + 0.3 * breakdown_count
    )
    risk_signal_normalized = (risk_signal - risk_signal.min()) / (risk_signal.max() - risk_signal.min())
    noise = rng.normal(0, 0.08, size=n_samples)
    probability = np.clip(risk_signal_normalized + noise, 0, 1)
    label = (rng.uniform(0, 1, size=n_samples) < probability).astype(int)

    return pd.DataFrame({
        "hours_since_last_maintenance": hours_since_maint,
        "average_daily_utilization_pct": utilization,
        "age_years": age_years,
        "historical_breakdown_count": breakdown_count,
        "breakdown_within_7_days": label,
    })


def train(save: bool = True) -> RandomForestClassifier:
    df = generate_synthetic_training_data()
    X = df[FEATURE_COLUMNS]
    y = df["breakdown_within_7_days"]

    model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=7, class_weight="balanced")
    model.fit(X, y)

    if save:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)

    return model


def load() -> RandomForestClassifier:
    if not MODEL_PATH.exists():
        return train(save=True)
    return joblib.load(MODEL_PATH)


def predict_failure_risk(rows: List[dict]) -> List[float]:
    """Returns a probability (0..1) of breakdown within 7 days per machine."""
    model = load()
    df = pd.DataFrame(rows)[FEATURE_COLUMNS]
    probabilities = model.predict_proba(df)[:, 1]
    return [round(float(p), 4) for p in probabilities]


if __name__ == "__main__":
    model = train()
    sample = pd.DataFrame([{
        "hours_since_last_maintenance": 1500,
        "average_daily_utilization_pct": 88,
        "age_years": 9,
        "historical_breakdown_count": 3,
    }])
    print("Sample failure risk probability:", model.predict_proba(sample)[0, 1])
