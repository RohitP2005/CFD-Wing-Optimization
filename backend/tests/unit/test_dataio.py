"""Unit tests for sampling and dataset storage."""

from __future__ import annotations

from src.dataio.schema import DATASET_COLUMNS, build_record
from src.dataio.storage import build_dataframe, write_dataset
from src.geometry.generator import generate_wing
from src.geometry.sampling import sample_designs
from src.simulation.analytic_adapter import AnalyticAdapter
from src.simulation.base_adapter import FlightCondition


def test_sampling_is_deterministic(bounds):
    a = sample_designs(bounds, "lhs", 8, seed=42)
    b = sample_designs(bounds, "lhs", 8, seed=42)
    assert [d.span_m for d in a] == [d.span_m for d in b]
    assert len(a) == 8


def test_sampled_designs_respect_chord_order(bounds):
    designs = sample_designs(bounds, "lhs", 20, seed=7)
    for design in designs:
        assert design.tip_chord_m <= design.root_chord_m


def test_write_dataset_creates_csv(tmp_path, bounds):
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
    result = AnalyticAdapter().evaluate(
        wing, FlightCondition(velocity_mps=20, aoa_deg=5)
    )
    record = build_record(
        wing,
        result,
        experiment_id="exp_test",
        config_hash="abc123",
        seed=42,
        experiment_tag="test",
    )
    frame = build_dataframe([record])
    assert list(frame.columns) == list(DATASET_COLUMNS)

    paths = write_dataset([record], tmp_path, "exp_test")
    assert paths["csv"].exists()
