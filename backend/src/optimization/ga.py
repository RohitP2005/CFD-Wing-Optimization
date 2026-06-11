"""Genetic algorithm for single-objective wing optimization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base import OptimizationResult, Optimizer, better_feasible
from .objective import BudgetExhausted, EvalRecord


@dataclass
class Individual:
    """A genome: continuous vector plus a discrete airfoil index."""

    vector: np.ndarray
    airfoil_index: int
    record: EvalRecord | None = None


class GeneticAlgorithm(Optimizer):
    """Real-coded GA with tournament selection, blend crossover, and elitism."""

    name = "ga"

    def __init__(
        self,
        evaluator,
        seed: int = 0,
        population_size: int = 40,
        generations: int = 30,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.2,
        elite: int = 2,
    ) -> None:
        super().__init__(evaluator, seed)
        self.population_size = int(population_size)
        self.generations = int(generations)
        self.crossover_rate = float(crossover_rate)
        self.mutation_rate = float(mutation_rate)
        self.elite = int(elite)
        self._rng = np.random.default_rng(seed)

    def _random_individual(self) -> Individual:
        space = self.evaluator.space
        return Individual(
            vector=space.random_vector(self._rng),
            airfoil_index=space.random_airfoil_index(self._rng),
        )

    def _evaluate(self, ind: Individual) -> bool:
        """Evaluate an individual in place. Returns False if budget exhausted."""
        space = self.evaluator.space
        params = space.to_parameters(ind.vector, ind.airfoil_index)
        try:
            ind.record = self.evaluator.evaluate(params)
        except BudgetExhausted:
            return False
        return True

    def _tournament(self, population: list[Individual]) -> Individual:
        i, j = self._rng.integers(len(population), size=2)
        a, b = population[i], population[j]
        if a.record is None:
            return b
        if b.record is None:
            return a
        return a if better_feasible(a.record, b.record) else b

    def _crossover(self, p1: Individual, p2: Individual) -> Individual:
        space = self.evaluator.space
        if self._rng.random() < self.crossover_rate:
            # Blend crossover (BLX-0.5) on continuous genes.
            alpha = self._rng.uniform(-0.5, 1.5, size=space.n_continuous)
            child_vec = p1.vector + alpha * (p2.vector - p1.vector)
        else:
            child_vec = p1.vector.copy()
        airfoil = p1.airfoil_index if self._rng.random() < 0.5 else p2.airfoil_index
        return Individual(vector=space.clip(child_vec), airfoil_index=airfoil)

    def _mutate(self, ind: Individual) -> None:
        space = self.evaluator.space
        span = space.upper - space.lower
        for d in range(space.n_continuous):
            if self._rng.random() < self.mutation_rate:
                ind.vector[d] += self._rng.normal(0.0, 0.1 * span[d])
        ind.vector = space.clip(ind.vector)
        if self._rng.random() < self.mutation_rate:
            ind.airfoil_index = space.random_airfoil_index(self._rng)

    def optimize(self) -> OptimizationResult:
        history: list[EvalRecord] = []
        convergence: list[dict[str, float]] = []
        best: EvalRecord | None = None

        population = [self._random_individual() for _ in range(self.population_size)]
        budget_ok = True
        for ind in population:
            if not self._evaluate(ind):
                budget_ok = False
                break
            history.append(ind.record)
            if better_feasible(ind.record, best):
                best = ind.record

        convergence.append(
            {"generation": 0.0, "best_cost": best.cost if best else float("inf")}
        )

        generation = 0
        while budget_ok and generation < self.generations:
            generation += 1
            # Elitism: carry the best individuals forward.
            ranked = sorted(
                (ind for ind in population if ind.record is not None),
                key=lambda x: (not x.record.feasible, x.record.cost),
            )
            next_pop: list[Individual] = ranked[: self.elite]

            while len(next_pop) < self.population_size:
                parent1 = self._tournament(population)
                parent2 = self._tournament(population)
                child = self._crossover(parent1, parent2)
                self._mutate(child)
                if not self._evaluate(child):
                    budget_ok = False
                    break
                history.append(child.record)
                if better_feasible(child.record, best):
                    best = child.record
                next_pop.append(child)

            population = next_pop
            convergence.append(
                {
                    "generation": float(generation),
                    "best_cost": best.cost if best else float("inf"),
                }
            )

        return OptimizationResult(
            algorithm=self.name,
            best=best,
            history=history,
            convergence=convergence,
            num_evaluations=self.evaluator.num_evaluations,
        )
