"""Common interface and data contracts for simulation adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..geometry.generator import WingGeometry


@dataclass(frozen=True)
class FlightCondition:
    """A single operating point for an aerodynamic evaluation."""

    velocity_mps: float
    aoa_deg: float
    air_density: float = 1.225

    @property
    def condition_id(self) -> str:
        return f"v{self.velocity_mps:g}_a{self.aoa_deg:g}"


@dataclass(frozen=True)
class SimulationResult:
    """Output contract for a single design-condition evaluation (FR-02)."""

    design_id: str
    condition: FlightCondition
    CL: float
    CD: float
    LD: float
    status: str
    solver: str
    iterations: int = 0
    residual_final: float = 0.0
    runtime_sec: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def converged(self) -> bool:
        return self.status == "converged"


class SimulationError(RuntimeError):
    """Raised when a simulation adapter fails irrecoverably for a case."""


class BaseSolverAdapter(ABC):
    """Abstract base class all solver adapters must implement."""

    name: str = "base"

    @abstractmethod
    def evaluate(
        self, geometry: WingGeometry, condition: FlightCondition
    ) -> SimulationResult:
        """Evaluate a single design at a single flight condition."""
        raise NotImplementedError
