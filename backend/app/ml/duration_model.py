"""
Predictive Duration Model
==========================

Purpose: manufacturing engineering-estimated durations
(`tasks.base_duration_minutes`) are almost always optimistic. This
model learns a correction factor from historical completed tasks so
the scheduler works with REALISTIC durations instead of nominal ones.

Features used (deliberately simple and explainable for a v1 — a
factory manager should be able to reason about why a prediction came
out the way it did). Chosen to be things this app actually tracks
per (task, eligible machine) pair — no operator/shift entity exists
in the schema, so those are intentionally left out in favor of a
signal that IS real:
    - base_duration_minutes       (engineering estimate for that machine)
    - machine_type (encoded)      (some machines run slower/faster)
    - job_priority_weight         (rushed high-priority jobs sometimes
                                    have more errors/rework)
    - machine_failure_risk_score  (a machine trending toward failure
                                    tends to run slower/less reliably
                                    before it actually breaks down)

Model: GradientBoostingRegressor (scikit-learn). Swappable for XGBoost
by changing `_build_pipeline()` only — the rest of this module's
public interface (`train`, `predict`, `load`) does not change.

In production, `train()` is run on a schedule (e.g. nightly) against
the growing `assignments` table (actual_start/actual_end vs.
base_duration_minutes), and the resulting model is persisted to disk
(or a model registry) and reloaded by the API process.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

MODEL_PATH = Path(__file__).parent / "artifacts" / "duration_model.joblib"

FEATURE_COLUMNS = [
    "base_duration_minutes",
    "machine_type",
    "job_priority_weight",
    "machine_failure_risk_score",
]
CATEGORICAL_COLUMNS = ["machine_type"]
NUMERIC_COLUMNS = ["base_duration_minutes", "job_priority_weight", "machine_failure_risk_score"]


@dataclasses.dataclass
class DurationPrediction:
    task_id: int
    predicted_duration_minutes: int


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ],
        remainder="passthrough",
    )
    model = GradientBoostingRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def generate_synthetic_training_data(n_samples: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Stand-in for querying historical completed tasks. Encodes a
    believable pattern: a machine trending toward failure runs slower
    and less predictably; higher-priority jobs get slightly better
    focus (less overrun); machine type shifts the baseline multiplier.
    """
    rng = np.random.default_rng(seed)

    machine_types = rng.choice(
        ["CNC_MILL", "LATHE", "ASSEMBLY_LINE", "WELDING_STATION"], size=n_samples
    )
    base_duration = rng.integers(15, 180, size=n_samples)
    failure_risk = rng.uniform(0.0, 1.0, size=n_samples)
    priority = rng.integers(1, 11, size=n_samples)

    machine_multiplier = pd.Series(machine_types).map(
        {"CNC_MILL": 1.05, "LATHE": 0.98, "ASSEMBLY_LINE": 1.10, "WELDING_STATION": 1.15}
    ).to_numpy()
    risk_penalty = 1.0 + failure_risk * 0.25
    priority_focus = 1.0 - (priority / 10.0) * 0.05
    noise = rng.normal(loc=1.0, scale=0.05, size=n_samples)

    actual_duration = (
        base_duration * machine_multiplier * risk_penalty * priority_focus * noise
    ).round().astype(int)
    actual_duration = np.clip(actual_duration, 5, None)

    return pd.DataFrame({
        "base_duration_minutes": base_duration,
        "machine_type": machine_types,
        "job_priority_weight": priority,
        "machine_failure_risk_score": failure_risk,
        "actual_duration_minutes": actual_duration,
    })


def train(save: bool = True) -> Pipeline:
    df = generate_synthetic_training_data()
    X = df[FEATURE_COLUMNS]
    y = df["actual_duration_minutes"]

    pipeline = _build_pipeline()
    pipeline.fit(X, y)

    if save:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, MODEL_PATH)

    return pipeline


def load() -> Pipeline:
    if not MODEL_PATH.exists():
        return train(save=True)
    return joblib.load(MODEL_PATH)


def predict_durations(rows: List[dict]) -> List[int]:
    """
    rows: list of dicts each containing FEATURE_COLUMNS keys plus a
    'task_id'. Returns predicted durations in the same order.
    """
    pipeline = load()
    df = pd.DataFrame(rows)[FEATURE_COLUMNS]
    predictions = pipeline.predict(df)
    return [max(1, int(round(p))) for p in predictions]


if __name__ == "__main__":
    model = train()
    sample = pd.DataFrame([{
        "base_duration_minutes": 60,
        "machine_type": "CNC_MILL",
        "job_priority_weight": 8,
        "machine_failure_risk_score": 0.35,
    }])
    print("Sample prediction (minutes):", model.predict(sample)[0])
