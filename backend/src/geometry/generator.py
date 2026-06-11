"""Parametric wing geometry generation and derived-metric computation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from .airfoil import Airfoil
from .validation import Bounds, validate_area, validate_parameters


@dataclass(frozen=True)
class WingParameters:
    """User-defined parametric wing inputs."""

    span_m: float
    root_chord_m: float
    tip_chord_m: float
    sweep_deg: float
    twist_deg: float
    airfoil_id: str

    @classmethod
    def from_mapping(cls, params: Mapping[str, object]) -> "WingParameters":
        return cls(
            span_m=float(params["span_m"]),
            root_chord_m=float(params["root_chord_m"]),
            tip_chord_m=float(params["tip_chord_m"]),
            sweep_deg=float(params["sweep_deg"]),
            twist_deg=float(params["twist_deg"]),
            airfoil_id=str(params["airfoil_id"]),
        )


@dataclass(frozen=True)
class WingGeometry:
    """Generated wing geometry with derived aerodynamic metrics."""

    design_id: str
    params: WingParameters
    wing_area_m2: float
    aspect_ratio: float
    taper_ratio: float
    mean_aerodynamic_chord_m: float

    def to_record(self) -> dict[str, object]:
        """Flatten parameters and metrics into a single record dict."""
        record = asdict(self.params)
        record.update(
            {
                "design_id": self.design_id,
                "wing_area_m2": self.wing_area_m2,
                "aspect_ratio": self.aspect_ratio,
                "taper_ratio": self.taper_ratio,
                "mean_aerodynamic_chord_m": self.mean_aerodynamic_chord_m,
            }
        )
        return record


def compute_metrics(params: WingParameters) -> dict[str, float]:
    """Compute derived planform metrics for a trapezoidal wing.

    Returns:
        Mapping with wing_area_m2, aspect_ratio, taper_ratio, and
        mean_aerodynamic_chord_m.
    """
    cr = params.root_chord_m
    ct = params.tip_chord_m
    b = params.span_m

    area = b * (cr + ct) / 2.0
    aspect_ratio = b**2 / area if area > 0 else 0.0
    taper = ct / cr if cr > 0 else 0.0
    # Mean aerodynamic chord for a trapezoidal planform.
    mac = (2.0 / 3.0) * cr * (1 + taper + taper**2) / (1 + taper) if cr > 0 else 0.0

    return {
        "wing_area_m2": area,
        "aspect_ratio": aspect_ratio,
        "taper_ratio": taper,
        "mean_aerodynamic_chord_m": mac,
    }


def generate_wing(
    params: WingParameters | Mapping[str, object],
    design_id: str,
    bounds: Bounds | None = None,
) -> WingGeometry:
    """Validate inputs and build a :class:`WingGeometry`.

    Args:
        params: Wing parameters as a dataclass or mapping.
        design_id: Unique identifier for the design.
        bounds: Optional bounds for validation. When provided, parameters and
            the computed wing area are validated.
    """
    if isinstance(params, Mapping):
        record = dict(params)
    else:
        record = asdict(params)

    if bounds is not None:
        validate_parameters(record, bounds)

    wing_params = WingParameters.from_mapping(record)
    # Ensure the airfoil is parseable early so failures surface here.
    Airfoil.from_naca4(wing_params.airfoil_id)

    metrics = compute_metrics(wing_params)
    if bounds is not None:
        validate_area(metrics["wing_area_m2"], bounds)

    return WingGeometry(
        design_id=design_id,
        params=wing_params,
        wing_area_m2=metrics["wing_area_m2"],
        aspect_ratio=metrics["aspect_ratio"],
        taper_ratio=metrics["taper_ratio"],
        mean_aerodynamic_chord_m=metrics["mean_aerodynamic_chord_m"],
    )


def export_geometry(geometry: WingGeometry, geometry_dir: str | Path) -> Path:
    """Persist geometry metadata as JSON and return the file path.

    Phase 1 exports a metadata descriptor rather than a meshed STL; the path
    contract matches FR-01 so later phases can swap in real CAD/mesh output.
    """
    out_dir = Path(geometry_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{geometry.design_id}.json"
    path.write_text(json.dumps(geometry.to_record(), indent=2), encoding="utf-8")
    return path
