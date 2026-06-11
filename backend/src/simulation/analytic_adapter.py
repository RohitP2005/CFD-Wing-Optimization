"""Analytic low-fidelity aerodynamic adapter (Phase 1 baseline solver).

This adapter uses lifting-line and thin-airfoil approximations to produce
physically plausible CL, CD, and L/D without an external CFD dependency. It
implements the same contract as a real solver so it can be swapped later.
"""

from __future__ import annotations

import math
import time

from ..geometry.airfoil import Airfoil
from ..geometry.generator import WingGeometry
from .base_adapter import (
    BaseSolverAdapter,
    FlightCondition,
    SimulationError,
    SimulationResult,
)

# Oswald span efficiency factor used for induced drag.
_OSWALD_EFFICIENCY = 0.85
# Approximate maximum lift coefficient before stall onset.
_CL_MAX = 1.4
# 2D lift-curve slope (per radian) from thin-airfoil theory.
_A0_PER_RAD = 2.0 * math.pi


class AnalyticAdapter(BaseSolverAdapter):
    """Low-fidelity analytic aerodynamic model."""

    name = "analytic"

    def evaluate(
        self, geometry: WingGeometry, condition: FlightCondition
    ) -> SimulationResult:
        start = time.perf_counter()
        try:
            cl, cd, status = self._aero_coefficients(geometry, condition)
        except Exception as exc:  # noqa: BLE001 - surface as adapter error
            raise SimulationError(
                f"Analytic evaluation failed for {geometry.design_id} "
                f"at {condition.condition_id}: {exc}"
            ) from exc

        ld = cl / cd if cd > 0 else 0.0
        runtime = time.perf_counter() - start

        return SimulationResult(
            design_id=geometry.design_id,
            condition=condition,
            CL=cl,
            CD=cd,
            LD=ld,
            status=status,
            solver=self.name,
            iterations=1,
            residual_final=0.0,
            runtime_sec=runtime,
            meta={"model": "lifting_line_thin_airfoil"},
        )

    def _aero_coefficients(
        self, geometry: WingGeometry, condition: FlightCondition
    ) -> tuple[float, float, str]:
        airfoil = Airfoil.from_naca4(geometry.params.airfoil_id)
        ar = geometry.aspect_ratio
        sweep_rad = math.radians(geometry.params.sweep_deg)

        # Zero-lift angle (deg): cambered airfoils have a negative alpha_L0.
        alpha_l0_deg = -airfoil.max_camber * 100.0

        # Geometric twist applies a partial washout/washin shift.
        effective_aoa_deg = condition.aoa_deg + 0.5 * geometry.params.twist_deg

        # 3D lift-curve slope with finite-span and sweep corrections.
        a0 = _A0_PER_RAD * math.cos(sweep_rad)
        a3d = a0 / (1.0 + a0 / (math.pi * _OSWALD_EFFICIENCY * ar)) if ar > 0 else 0.0

        alpha_rad = math.radians(effective_aoa_deg - alpha_l0_deg)
        cl = a3d * alpha_rad

        status = "converged"
        if cl > _CL_MAX:
            # Post-stall behaviour: clamp lift and flag the case.
            cl = _CL_MAX
            status = "stall_limited"

        # Parasite drag grows with thickness; induced drag scales with CL^2.
        cd0 = 0.006 + 0.01 * airfoil.thickness
        cd_induced = cl**2 / (math.pi * _OSWALD_EFFICIENCY * ar) if ar > 0 else 0.0
        cd = cd0 + cd_induced

        return cl, cd, status
