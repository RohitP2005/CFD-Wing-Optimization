"""Regression metrics for surrogate evaluation (RMSE, MAE, R2)."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute RMSE, MAE, and R2 for one target."""
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return {"rmse": rmse, "mae": mae, "r2": r2}


def meets_threshold(
    metrics_by_target: dict[str, dict[str, float]],
    threshold: float,
    targets: tuple[str, ...],
) -> bool:
    """Return True when every named target's R2 meets the threshold."""
    return all(metrics_by_target[t]["r2"] >= threshold for t in targets)
