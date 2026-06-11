"""Field artifact layer for higher-fidelity solver adapters (Phase 5).

Defines the in-memory field container and the on-disk artifact contract
(surface distribution CSV, ``.npz`` field grid, and a JSON sidecar) used by
field-producing solver adapters and the flow visualizations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class FieldData:
    """Spatial flow field and surface distribution for one design-condition.

    Coordinates are normalized by chord (x/c, y/c); the freestream speed is
    normalized to 1, so pressure is stored directly as a coefficient (Cp).
    """

    design_id: str
    condition_id: str
    solver: str
    x_grid: np.ndarray
    y_grid: np.ndarray
    pressure: np.ndarray
    velocity_x: np.ndarray
    velocity_y: np.ndarray
    surface_x: np.ndarray
    surface_cp: np.ndarray
    status: str = "converged"
    iterations: int = 0
    residual_final: float = 0.0
    runtime_sec: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def grid_shape(self) -> tuple[int, int]:
        return tuple(self.x_grid.shape)  # type: ignore[return-value]


def _case_dir(fields_dir: str | Path, design_id: str, condition_id: str) -> Path:
    return Path(fields_dir) / design_id / condition_id


def write_fields(data: FieldData, fields_dir: str | Path) -> Path:
    """Persist a field as surface CSV + ``.npz`` grid + JSON sidecar.

    Returns the path to the JSON sidecar, which references the other files.
    """
    out_dir = _case_dir(fields_dir, data.design_id, data.condition_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    surface_path = out_dir / "surface.csv"
    header = "x_over_c,Cp"
    rows = np.column_stack([data.surface_x, data.surface_cp])
    np.savetxt(surface_path, rows, delimiter=",", header=header, comments="")

    field_path = out_dir / "field.npz"
    np.savez_compressed(
        field_path,
        x_grid=data.x_grid,
        y_grid=data.y_grid,
        pressure=data.pressure,
        velocity_x=data.velocity_x,
        velocity_y=data.velocity_y,
    )

    sidecar_path = out_dir / "field.json"
    sidecar = {
        "design_id": data.design_id,
        "condition_id": data.condition_id,
        "solver": data.solver,
        "grid_shape": list(data.grid_shape),
        "fields": ["pressure", "velocity_x", "velocity_y"],
        "units": {"pressure": "Cp", "velocity": "U_inf"},
        "surface_file": str(surface_path),
        "field_file": str(field_path),
        "status": data.status,
        "iterations": data.iterations,
        "residual_final": data.residual_final,
        "runtime_sec": data.runtime_sec,
        "meta": data.meta,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return sidecar_path


def load_fields(sidecar_path: str | Path) -> FieldData:
    """Reconstruct a :class:`FieldData` from a JSON sidecar and its artifacts."""
    sidecar_path = Path(sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    surface = np.loadtxt(sidecar["surface_file"], delimiter=",", skiprows=1)
    surface_x = surface[:, 0]
    surface_cp = surface[:, 1]

    with np.load(sidecar["field_file"]) as grid:
        x_grid = grid["x_grid"]
        y_grid = grid["y_grid"]
        pressure = grid["pressure"]
        velocity_x = grid["velocity_x"]
        velocity_y = grid["velocity_y"]

    return FieldData(
        design_id=sidecar["design_id"],
        condition_id=sidecar["condition_id"],
        solver=sidecar["solver"],
        x_grid=x_grid,
        y_grid=y_grid,
        pressure=pressure,
        velocity_x=velocity_x,
        velocity_y=velocity_y,
        surface_x=surface_x,
        surface_cp=surface_cp,
        status=sidecar.get("status", "converged"),
        iterations=int(sidecar.get("iterations", 0)),
        residual_final=float(sidecar.get("residual_final", 0.0)),
        runtime_sec=float(sidecar.get("runtime_sec", 0.0)),
        meta=sidecar.get("meta", {}),
    )
