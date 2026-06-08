"""Parameter validation and design-variable bounds handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


# Design variables that participate in bounds checking.
DESIGN_VARIABLES: tuple[str, ...] = (
    "span_m",
    "root_chord_m",
    "tip_chord_m",
    "sweep_deg",
    "twist_deg",
)


class ValidationError(ValueError):
    """Raised when a wing parameter set violates bounds or constraints."""


@dataclass(frozen=True)
class Bounds:
    """Design-variable bounds and feasibility constraints."""

    ranges: Mapping[str, tuple[float, float]]
    airfoils: Sequence[str]
    enforce_tip_le_root: bool = True
    wing_area_m2: tuple[float, float] | None = None

    @classmethod
    def from_config(cls, config: Mapping) -> "Bounds":
        """Build a :class:`Bounds` instance from a parsed bounds config."""
        raw_ranges = config["bounds"]
        ranges = {key: (float(lo), float(hi)) for key, (lo, hi) in raw_ranges.items()}
        constraints = config.get("constraints", {})
        area = constraints.get("wing_area_m2")
        wing_area = (float(area[0]), float(area[1])) if area else None
        return cls(
            ranges=ranges,
            airfoils=tuple(config.get("airfoils", [])),
            enforce_tip_le_root=bool(constraints.get("enforce_tip_le_root", True)),
            wing_area_m2=wing_area,
        )


def _check_range(name: str, value: float, bounds: tuple[float, float]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ValidationError(
            f"{name}={value} is outside allowed range [{low}, {high}]"
        )


def validate_parameters(params: Mapping[str, object], bounds: Bounds) -> None:
    """Validate a wing parameter set against design-variable bounds.

    Raises:
        ValidationError: If any required variable is missing, out of range,
            references an unknown airfoil, or violates a feasibility constraint.
    """
    for name in DESIGN_VARIABLES:
        if name not in params:
            raise ValidationError(f"Missing required parameter: {name}")
        if name in bounds.ranges:
            _check_range(name, float(params[name]), bounds.ranges[name])

    airfoil = params.get("airfoil_id")
    if airfoil is None:
        raise ValidationError("Missing required parameter: airfoil_id")
    if bounds.airfoils and airfoil not in bounds.airfoils:
        raise ValidationError(
            f"airfoil_id={airfoil!r} is not in allowed set {tuple(bounds.airfoils)}"
        )

    if bounds.enforce_tip_le_root:
        if float(params["tip_chord_m"]) > float(params["root_chord_m"]):
            raise ValidationError(
                "tip_chord_m must be <= root_chord_m "
                f"(got tip={params['tip_chord_m']}, root={params['root_chord_m']})"
            )


def validate_area(area_m2: float, bounds: Bounds) -> None:
    """Validate that a computed wing area is within the configured band."""
    if bounds.wing_area_m2 is not None:
        _check_range("wing_area_m2", area_m2, bounds.wing_area_m2)


def iter_design_variables() -> Iterable[str]:
    """Return the ordered design-variable names."""
    return DESIGN_VARIABLES
