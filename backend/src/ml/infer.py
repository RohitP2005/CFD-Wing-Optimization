"""Inference helpers and a surrogate-backed solver adapter.

The :class:`SurrogateAdapter` implements the same interface as a real solver,
so a trained surrogate can be dropped into the optimization loop to replace
expensive CFD calls (surrogate-in-the-loop optimization).
"""

from __future__ import annotations

import time

from ..geometry.generator import WingGeometry
from ..simulation.base_adapter import (
    BaseSolverAdapter,
    FlightCondition,
    SimulationResult,
)
from .features import encode_row
from .train import SurrogateBundle, load_bundle


def predict_one(
    bundle: SurrogateBundle,
    *,
    span_m: float,
    root_chord_m: float,
    tip_chord_m: float,
    sweep_deg: float,
    twist_deg: float,
    aoa_deg: float,
    velocity_mps: float,
    airfoil_id: str,
) -> dict[str, float]:
    """Predict CL, CD, and L/D for a single design-condition row."""
    row = {
        "span_m": span_m,
        "root_chord_m": root_chord_m,
        "tip_chord_m": tip_chord_m,
        "sweep_deg": sweep_deg,
        "twist_deg": twist_deg,
        "aoa_deg": aoa_deg,
        "velocity_mps": velocity_mps,
        "airfoil_id": airfoil_id,
    }
    X = encode_row(row, bundle.spec)
    preds = bundle.predict(X)
    return {target: float(values[0]) for target, values in preds.items()}


class SurrogateAdapter(BaseSolverAdapter):
    """Solver adapter that returns surrogate predictions instead of CFD."""

    name = "surrogate"

    def __init__(self, bundle: SurrogateBundle) -> None:
        self.bundle = bundle
        # Single-row predictions are far cheaper single-threaded; forcing n_jobs=1
        # avoids per-call thread-pool overhead and noisy joblib warnings.
        for model in bundle.models.values():
            if hasattr(model, "n_jobs"):
                model.n_jobs = 1

    @classmethod
    def from_path(cls, model_path: str) -> "SurrogateAdapter":
        return cls(load_bundle(model_path))

    def evaluate(
        self, geometry: WingGeometry, condition: FlightCondition
    ) -> SimulationResult:
        start = time.perf_counter()
        preds = predict_one(
            self.bundle,
            span_m=geometry.params.span_m,
            root_chord_m=geometry.params.root_chord_m,
            tip_chord_m=geometry.params.tip_chord_m,
            sweep_deg=geometry.params.sweep_deg,
            twist_deg=geometry.params.twist_deg,
            aoa_deg=condition.aoa_deg,
            velocity_mps=condition.velocity_mps,
            airfoil_id=geometry.params.airfoil_id,
        )
        cl = preds.get("CL", 0.0)
        cd = preds.get("CD", 1e-6)
        # Prefer a directly predicted L/D when present; otherwise derive it.
        ld = preds.get("LD")
        if ld is None:
            ld = cl / cd if cd > 0 else 0.0

        return SimulationResult(
            design_id=geometry.design_id,
            condition=condition,
            CL=cl,
            CD=cd,
            LD=ld,
            status="converged",
            solver=self.name,
            iterations=0,
            residual_final=0.0,
            runtime_sec=time.perf_counter() - start,
            meta={"model": self.bundle.model_name},
        )
