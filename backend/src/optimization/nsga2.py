"""NSGA-II multi-objective optimizer (maximize CL, minimize CD)."""

from __future__ import annotations

import numpy as np

from .base import OptimizationResult, Optimizer
from .ga import Individual
from .objective import BudgetExhausted, EvalRecord


def _dominates(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Return True if objective vector a Pareto-dominates b (both minimized)."""
    return a[0] <= b[0] and a[1] <= b[1] and (a[0] < b[0] or a[1] < b[1])


def fast_non_dominated_sort(objs: list[tuple[float, float]]) -> list[list[int]]:
    """Partition indices into Pareto fronts (front 0 is non-dominated)."""
    n = len(objs)
    dominated: list[list[int]] = [[] for _ in range(n)]
    dom_count = [0] * n
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if _dominates(objs[p], objs[q]):
                dominated[p].append(q)
            elif _dominates(objs[q], objs[p]):
                dom_count[p] += 1
        if dom_count[p] == 0:
            fronts[0].append(p)

    i = 0
    while fronts[i]:
        nxt: list[int] = []
        for p in fronts[i]:
            for q in dominated[p]:
                dom_count[q] -= 1
                if dom_count[q] == 0:
                    nxt.append(q)
        i += 1
        fronts.append(nxt)
    return fronts[:-1]


def crowding_distance(objs: list[tuple[float, float]], front: list[int]) -> dict[int, float]:
    """Compute crowding distance for members of a front."""
    distance = {i: 0.0 for i in front}
    if len(front) <= 2:
        return {i: float("inf") for i in front}

    for m in range(2):
        ordered = sorted(front, key=lambda i: objs[i][m])
        distance[ordered[0]] = float("inf")
        distance[ordered[-1]] = float("inf")
        lo = objs[ordered[0]][m]
        hi = objs[ordered[-1]][m]
        span = hi - lo
        if span == 0:
            continue
        for k in range(1, len(ordered) - 1):
            prev_obj = objs[ordered[k - 1]][m]
            next_obj = objs[ordered[k + 1]][m]
            distance[ordered[k]] += (next_obj - prev_obj) / span
    return distance


class NSGA2(Optimizer):
    """Elitist non-dominated sorting genetic algorithm."""

    name = "nsga2"

    def __init__(
        self,
        evaluator,
        seed: int = 0,
        population_size: int = 40,
        generations: int = 30,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.2,
    ) -> None:
        super().__init__(evaluator, seed)
        self.population_size = int(population_size)
        self.generations = int(generations)
        self.crossover_rate = float(crossover_rate)
        self.mutation_rate = float(mutation_rate)
        self._rng = np.random.default_rng(seed)

    def _random_individual(self) -> Individual:
        space = self.evaluator.space
        return Individual(
            vector=space.random_vector(self._rng),
            airfoil_index=space.random_airfoil_index(self._rng),
        )

    def _evaluate(self, ind: Individual) -> bool:
        space = self.evaluator.space
        params = space.to_parameters(ind.vector, ind.airfoil_index)
        try:
            ind.record = self.evaluator.evaluate(params)
        except BudgetExhausted:
            return False
        return True

    def _crossover(self, p1: Individual, p2: Individual) -> Individual:
        space = self.evaluator.space
        if self._rng.random() < self.crossover_rate:
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

    def _make_offspring(self, population: list[Individual]) -> Individual:
        i, j = self._rng.integers(len(population), size=2)
        child = self._crossover(population[i], population[j])
        self._mutate(child)
        return child

    def optimize(self) -> OptimizationResult:
        history: list[EvalRecord] = []

        population = [self._random_individual() for _ in range(self.population_size)]
        budget_ok = True
        for ind in population:
            if not self._evaluate(ind):
                budget_ok = False
                break
            history.append(ind.record)

        population = [ind for ind in population if ind.record is not None]

        generation = 0
        while budget_ok and generation < self.generations:
            generation += 1
            offspring: list[Individual] = []
            for _ in range(self.population_size):
                child = self._make_offspring(population)
                if not self._evaluate(child):
                    budget_ok = False
                    break
                history.append(child.record)
                offspring.append(child)

            combined = population + offspring
            objs = [ind.record.objectives for ind in combined]
            fronts = fast_non_dominated_sort(objs)

            new_pop: list[Individual] = []
            for front in fronts:
                if len(new_pop) + len(front) <= self.population_size:
                    new_pop.extend(combined[i] for i in front)
                else:
                    distances = crowding_distance(objs, front)
                    ordered = sorted(front, key=lambda i: distances[i], reverse=True)
                    remaining = self.population_size - len(new_pop)
                    new_pop.extend(combined[i] for i in ordered[:remaining])
                    break
            population = new_pop

        # Final Pareto front from the last population.
        objs = [ind.record.objectives for ind in population]
        fronts = fast_non_dominated_sort(objs) if objs else []
        pareto = [population[i].record for i in fronts[0]] if fronts else []
        pareto = sorted(pareto, key=lambda r: r.objectives[0])

        best = min(pareto, key=lambda r: r.metrics["CD"]) if pareto else None

        return OptimizationResult(
            algorithm=self.name,
            best=best,
            history=history,
            convergence=[],
            pareto=pareto,
            num_evaluations=self.evaluator.num_evaluations,
        )
