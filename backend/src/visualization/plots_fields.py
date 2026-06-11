"""Flow-field visualizations from solver field artifacts (Phase 5).

Renders surface pressure, pressure/velocity contours, and streamlines from a
:class:`~src.simulation.fields.FieldData`. Each function follows the shared
save-or-return contract so it serves both the CLI and the dashboard.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..simulation.fields import FieldData
from .common import _figure, save_or_return


def _airfoil_overlay(ax) -> None:
    ax.set_xlabel("x/c")
    ax.set_ylabel("y/c")
    ax.set_aspect("equal", adjustable="box")


def plot_surface_cp(data: FieldData, path: str | Path | None = None):
    """Plot surface pressure coefficient around the section (Cp vs x/c)."""
    fig, ax = _figure(figsize=(6, 4))
    ax.plot(data.surface_x, data.surface_cp, color="tab:blue", lw=1.2)
    ax.invert_yaxis()  # conventional Cp orientation (suction up)
    ax.set_xlabel("x/c")
    ax.set_ylabel("Cp")
    ax.set_title(f"Surface Cp ({data.solver}, {data.condition_id})")
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)


def plot_pressure_contour(data: FieldData, path: str | Path | None = None):
    """Filled contour of the pressure coefficient field."""
    fig, ax = _figure(figsize=(7, 4))
    cf = ax.contourf(
        data.x_grid, data.y_grid, data.pressure, levels=30, cmap="coolwarm"
    )
    fig.colorbar(cf, ax=ax, label="Cp")
    ax.set_title(f"Pressure field ({data.solver}, {data.condition_id})")
    _airfoil_overlay(ax)
    return save_or_return(fig, path)


def plot_velocity_contour(data: FieldData, path: str | Path | None = None):
    """Filled contour of velocity magnitude (normalized by freestream)."""
    speed = np.sqrt(data.velocity_x**2 + data.velocity_y**2)
    fig, ax = _figure(figsize=(7, 4))
    cf = ax.contourf(data.x_grid, data.y_grid, speed, levels=30, cmap="viridis")
    fig.colorbar(cf, ax=ax, label="|V| / U")
    ax.set_title(f"Velocity magnitude ({data.solver}, {data.condition_id})")
    _airfoil_overlay(ax)
    return save_or_return(fig, path)


def plot_streamlines(data: FieldData, path: str | Path | None = None):
    """Streamlines of the flow around the section."""
    fig, ax = _figure(figsize=(7, 4))
    u = np.nan_to_num(data.velocity_x)
    v = np.nan_to_num(data.velocity_y)
    speed = np.sqrt(u**2 + v**2)
    # streamplot needs strictly increasing 1D coordinate vectors.
    x = data.x_grid[0, :]
    y = data.y_grid[:, 0]
    ax.streamplot(x, y, u, v, color=speed, cmap="viridis", density=1.2, linewidth=0.7)
    ax.set_title(f"Streamlines ({data.solver}, {data.condition_id})")
    _airfoil_overlay(ax)
    return save_or_return(fig, path)
