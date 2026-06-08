"""Panel-method field-producing adapter (Phase 5 default field solver).

This adapter reuses the analytic lifting-line model for the reported CL/CD/LD
so coefficients stay consistent with the baseline, and additionally constructs
a 2D potential-flow field around the wing's root section for visualization
(pressure contour, velocity field, streamlines, and surface Cp).

The field is a superposition of a uniform stream, a bound vortex sized to the
section circulation (Kutta-Joukowski), and a source/sink pair representing the
airfoil's thickness displacement. It is intentionally low fidelity: a fast,
dependency-light stand-in until an external RANS solver is wrapped.
"""

from __future__ import annotations

import math
import time

import numpy as np

from ..geometry.airfoil import Airfoil
from ..geometry.generator import WingGeometry
from .analytic_adapter import AnalyticAdapter
from .base_adapter import BaseSolverAdapter, FlightCondition, SimulationResult
from .fields import FieldData

# Field grid extent in chord-normalized coordinates.
_X_RANGE = (-0.6, 1.6)
_Y_RANGE = (-0.8, 0.8)


class Panel2DAdapter(BaseSolverAdapter):
    """Low-fidelity field-producing adapter built on potential-flow elements."""

    name = "panel2d"

    def __init__(self, n_panels: int = 160, grid_nx: int = 140, grid_ny: int = 110):
        self.n_panels = int(n_panels)
        self.grid_nx = int(grid_nx)
        self.grid_ny = int(grid_ny)
        self._analytic = AnalyticAdapter()

    def evaluate(
        self, geometry: WingGeometry, condition: FlightCondition
    ) -> SimulationResult:
        """Return coefficients identical to the analytic baseline."""
        base = self._analytic.evaluate(geometry, condition)
        meta = dict(base.meta)
        meta["model"] = "panel2d_potential_flow"
        return SimulationResult(
            design_id=base.design_id,
            condition=base.condition,
            CL=base.CL,
            CD=base.CD,
            LD=base.LD,
            status=base.status,
            solver=self.name,
            iterations=self.n_panels,
            residual_final=0.0,
            runtime_sec=base.runtime_sec,
            meta=meta,
        )

    @property
    def supports_fields(self) -> bool:
        return True

    def compute_field(
        self,
        geometry: WingGeometry,
        condition: FlightCondition,
        result: SimulationResult | None = None,
    ) -> FieldData:
        """Construct the 2D potential-flow field for the root section."""
        start = time.perf_counter()
        if result is None:
            result = self.evaluate(geometry, condition)

        airfoil = Airfoil.from_naca4(geometry.params.airfoil_id)
        alpha = math.radians(condition.aoa_deg)
        cl = float(result.CL)

        # Surface coordinates (x/c, y/c) for the root section.
        xs = np.linspace(0.0, 1.0, self.n_panels)
        yc = airfoil.camber_line(xs)
        yt = airfoil.thickness_distribution(xs)
        upper = yc + yt
        lower = yc - yt

        # Field grid.
        gx = np.linspace(_X_RANGE[0], _X_RANGE[1], self.grid_nx)
        gy = np.linspace(_Y_RANGE[0], _Y_RANGE[1], self.grid_ny)
        x_grid, y_grid = np.meshgrid(gx, gy)

        u, v = self._velocity_field(x_grid, y_grid, alpha, cl, airfoil.thickness)
        speed_sq = u**2 + v**2
        cp = 1.0 - speed_sq

        # Mask points inside the airfoil body.
        inside = self._inside_mask(x_grid, y_grid, xs, yc, yt)
        cp = np.where(inside, np.nan, cp)
        u = np.where(inside, np.nan, u)
        v = np.where(inside, np.nan, v)

        # Surface Cp sampled just outside the upper and lower surfaces.
        surface_x, surface_cp = self._surface_cp(
            xs, upper, lower, yc, alpha, cl, airfoil.thickness
        )

        runtime = time.perf_counter() - start
        return FieldData(
            design_id=geometry.design_id,
            condition_id=condition.condition_id,
            solver=self.name,
            x_grid=x_grid,
            y_grid=y_grid,
            pressure=cp,
            velocity_x=u,
            velocity_y=v,
            surface_x=surface_x,
            surface_cp=surface_cp,
            status=result.status,
            iterations=self.n_panels,
            residual_final=0.0,
            runtime_sec=runtime,
            meta={"airfoil": geometry.params.airfoil_id, "aoa_deg": condition.aoa_deg},
        )

    # -- Potential-flow elements -------------------------------------------

    def _velocity_field(self, x, y, alpha, cl, thickness):
        """Superpose freestream, bound vortex, and thickness source/sink."""
        u = np.full_like(x, math.cos(alpha))
        v = np.full_like(x, math.sin(alpha))

        # Bound vortex at the quarter chord sized to the section circulation.
        # Kutta-Joukowski (U=c=1): Gamma = 0.5 * CL. Sign gives upper suction.
        gamma = 0.5 * cl
        u_v, v_v = self._vortex(x, y, 0.25, 0.0, gamma)
        u += u_v
        v += v_v

        # Thickness displacement: source near LE, sink near TE.
        strength = max(thickness, 0.0) * 0.6
        u_s1, v_s1 = self._source(x, y, 0.05, 0.0, strength)
        u_s2, v_s2 = self._source(x, y, 0.95, 0.0, -strength)
        u += u_s1 + u_s2
        v += v_s1 + v_s2
        return u, v

    @staticmethod
    def _vortex(x, y, x0, y0, gamma):
        dx = x - x0
        dy = y - y0
        r2 = dx**2 + dy**2 + 1e-6
        # Clockwise circulation for positive lift (suction on the upper side).
        u = gamma / (2.0 * math.pi) * dy / r2
        v = -gamma / (2.0 * math.pi) * dx / r2
        return u, v

    @staticmethod
    def _source(x, y, x0, y0, strength):
        dx = x - x0
        dy = y - y0
        r2 = dx**2 + dy**2 + 1e-6
        u = strength / (2.0 * math.pi) * dx / r2
        v = strength / (2.0 * math.pi) * dy / r2
        return u, v

    @staticmethod
    def _inside_mask(x_grid, y_grid, xs, yc, yt):
        """Boolean mask of grid points inside the airfoil body."""
        in_chord = (x_grid >= 0.0) & (x_grid <= 1.0)
        yc_i = np.interp(x_grid, xs, yc, left=0.0, right=0.0)
        yt_i = np.interp(x_grid, xs, yt, left=0.0, right=0.0)
        return in_chord & (np.abs(y_grid - yc_i) <= yt_i)

    def _surface_cp(self, xs, upper, lower, yc, alpha, cl, thickness):
        """Cp on a closed loop around the section (upper TE->LE, lower LE->TE)."""
        eps = 0.01
        # Upper surface sampled from trailing edge to leading edge.
        xu = xs[::-1]
        yu = upper[::-1] + eps
        # Lower surface sampled from leading edge to trailing edge.
        xl = xs
        yl = lower - eps

        loop_x = np.concatenate([xu, xl])
        loop_y = np.concatenate([yu, yl])
        u, v = self._velocity_field(loop_x, loop_y, alpha, cl, thickness)
        cp = 1.0 - (u**2 + v**2)
        return loop_x, cp
