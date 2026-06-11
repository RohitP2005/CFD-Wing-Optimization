"""Constraint handling and penalty computation for optimization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstraintSet:
    """Optimization constraints and penalty weighting."""

    wing_area_m2: tuple[float, float] | None
    penalty_weight: float = 100.0

    @classmethod
    def from_config(cls, config: dict) -> "ConstraintSet":
        area = config.get("wing_area_m2")
        band = (float(area[0]), float(area[1])) if area else None
        return cls(
            wing_area_m2=band,
            penalty_weight=float(config.get("penalty_weight", 100.0)),
        )

    def area_violation(self, area_m2: float) -> float:
        """Return the magnitude of wing-area constraint violation (0 if feasible)."""
        if self.wing_area_m2 is None:
            return 0.0
        low, high = self.wing_area_m2
        if area_m2 < low:
            return low - area_m2
        if area_m2 > high:
            return area_m2 - high
        return 0.0

    def penalty(self, area_m2: float) -> float:
        """Return the weighted penalty for a design's constraint violations."""
        return self.penalty_weight * self.area_violation(area_m2)

    def is_feasible(self, area_m2: float) -> bool:
        """Return True when the design satisfies all constraints."""
        return self.area_violation(area_m2) == 0.0
