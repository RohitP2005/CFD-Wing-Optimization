"""Geometry visualizations: airfoil profile, camber, thickness, and planform."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..geometry.airfoil import Airfoil
from ..geometry.generator import WingParameters
from .common import _figure, save_or_return


def plot_airfoil(airfoil_id: str, path: str | Path | None = None, n: int = 120):
    """Plot the airfoil profile, camber line, and thickness distribution."""
    airfoil = Airfoil.from_naca4(airfoil_id)
    x = np.linspace(0.0, 1.0, n)
    yc = airfoil.camber_line(x)
    yt = airfoil.thickness_distribution(x)
    upper = yc + yt
    lower = yc - yt

    fig, ax = _figure(figsize=(7, 3.5))
    ax.plot(x, upper, color="tab:blue", label="upper")
    ax.plot(x, lower, color="tab:blue")
    ax.plot(x, yc, color="tab:red", linestyle="--", label="camber")
    ax.fill_between(x, lower, upper, color="tab:blue", alpha=0.1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x/c")
    ax.set_ylabel("y/c")
    ax.set_title(f"Airfoil: {airfoil_id}")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)


def plot_planform(params: WingParameters, path: str | Path | None = None):
    """Plot the half-span wing planform (leading and trailing edges)."""
    b = params.span_m
    cr = params.root_chord_m
    ct = params.tip_chord_m
    half = b / 2.0
    sweep = np.radians(params.sweep_deg)

    # Quarter-chord sweep applied along the half-span.
    le_root_x = 0.0
    le_tip_x = le_root_x + half * np.tan(sweep)

    ys = np.array([0.0, half])
    le_x = np.array([le_root_x, le_tip_x])
    te_x = np.array([le_root_x - cr, le_tip_x - ct])

    fig, ax = _figure(figsize=(6, 4))
    # Plot both half-spans for a full planform view.
    for sign in (1, -1):
        ax.plot(sign * ys, le_x, color="tab:blue")
        ax.plot(sign * ys, te_x, color="tab:blue")
        ax.plot([sign * half, sign * half], [le_tip_x, le_tip_x - ct], color="tab:blue")
    ax.plot([0, 0], [le_root_x, le_root_x - cr], color="tab:blue")
    ax.fill_between(
        np.concatenate([-ys[::-1], ys]),
        np.concatenate([te_x[::-1], te_x]),
        np.concatenate([le_x[::-1], le_x]),
        color="tab:blue",
        alpha=0.1,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("span (m)")
    ax.set_ylabel("chordwise (m)")
    ax.set_title(
        f"Planform: b={b:.2f} cr={cr:.2f} ct={ct:.2f} sweep={params.sweep_deg:.0f} deg"
    )
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)
