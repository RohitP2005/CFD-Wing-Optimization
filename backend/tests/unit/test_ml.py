"""Unit tests for the Phase 3 ML surrogate package."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.dataset import build_dataset, design_wise_split
from src.ml.features import build_feature_spec, encode_frame
from src.ml.infer import SurrogateAdapter
from src.ml.train import save_bundle, train_surrogate
from src.simulation.base_adapter import FlightCondition
from src.geometry.generator import generate_wing


AIRFOILS = ["NACA0012", "NACA2412", "NACA4412"]


def _synthetic_frame(n_designs: int = 60, seed: int = 0) -> pd.DataFrame:
    """Build a synthetic, learnable dataset with a known functional form."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_designs):
        span = rng.uniform(1.0, 2.0)
        root = rng.uniform(0.15, 0.50)
        tip = rng.uniform(0.05, root)
        sweep = rng.uniform(0, 30)
        twist = rng.uniform(-5, 5)
        airfoil = AIRFOILS[d % len(AIRFOILS)]
        for aoa in (-4, 0, 4, 8):
            for vel in (15, 20, 25):
                cl = 0.1 * aoa + 0.5 * span + 0.05 * twist
                cd = 0.01 + 0.002 * abs(aoa) + 0.01 * tip
                rows.append(
                    {
                        "design_id": f"d{d:03d}",
                        "span_m": span,
                        "root_chord_m": root,
                        "tip_chord_m": tip,
                        "sweep_deg": sweep,
                        "twist_deg": twist,
                        "airfoil_id": airfoil,
                        "aoa_deg": aoa,
                        "velocity_mps": vel,
                        "CL": cl,
                        "CD": cd,
                        "LD": cl / cd,
                    }
                )
    return pd.DataFrame(rows)


def test_feature_encoding_shape_and_onehot():
    spec = build_feature_spec(AIRFOILS)
    frame = _synthetic_frame(2)
    X = encode_frame(frame, spec)
    assert X.shape[1] == spec.n_features
    # One-hot block sums to 1 per row (each row has a known airfoil).
    onehot = X[:, len(spec.continuous):]
    assert np.allclose(onehot.sum(axis=1), 1.0)


def test_design_wise_split_has_no_leakage():
    frame = _synthetic_frame(30)
    train, test = design_wise_split(frame, test_fraction=0.3, seed=1)
    train_ids = set(train["design_id"])
    test_ids = set(test["design_id"])
    assert train_ids.isdisjoint(test_ids)


def test_train_surrogate_learns_synthetic(tmp_path):
    frame = _synthetic_frame(80)
    dataset = build_dataset(frame, airfoils=AIRFOILS, test_fraction=0.2, seed=42)
    bundle, report = train_surrogate(
        dataset, "random_forest", seed=42, threshold=0.90
    )
    # The relationship is smooth and learnable; expect strong R2.
    assert report.metrics["CL"]["r2"] > 0.9
    assert report.metrics["CD"]["r2"] > 0.9

    paths = save_bundle(bundle, report, tmp_path, "surrogate_test")
    assert paths["model"].exists()
    assert paths["report"].exists()


def test_surrogate_adapter_matches_solver_interface(tmp_path, bounds):
    frame = _synthetic_frame(80)
    dataset = build_dataset(frame, airfoils=AIRFOILS, test_fraction=0.2, seed=42)
    bundle, _ = train_surrogate(dataset, "random_forest", seed=42)

    adapter = SurrogateAdapter(bundle)
    wing = generate_wing(
        {
            "span_m": 1.5,
            "root_chord_m": 0.30,
            "tip_chord_m": 0.15,
            "sweep_deg": 10.0,
            "twist_deg": 2.0,
            "airfoil_id": "NACA2412",
        },
        design_id="wing_000000",
        bounds=bounds,
    )
    result = adapter.evaluate(wing, FlightCondition(velocity_mps=20, aoa_deg=4))
    assert result.solver == "surrogate"
    assert result.CD > 0
    assert np.isfinite(result.LD)
