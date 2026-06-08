"""Post-processing and quality-control checks for simulation results."""

from __future__ import annotations

from .base_adapter import SimulationResult


def quality_flags(result: SimulationResult) -> list[str]:
    """Return a list of QC flags for a result. Empty means it passed cleanly."""
    flags: list[str] = []
    if not result.converged and result.status != "stall_limited":
        flags.append(f"non_converged:{result.status}")
    if result.CD <= 0:
        flags.append("non_positive_cd")
    if abs(result.CL) > 2.0:
        flags.append("implausible_cl")
    if result.LD < 0:
        flags.append("negative_ld")
    return flags


def is_acceptable(result: SimulationResult) -> bool:
    """Return True when a result passes all quality gates."""
    return not quality_flags(result)
