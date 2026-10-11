import time
import itertools
import numpy as np
from typing import Callable, Optional, Tuple

from qiskit_algorithms.optimizers import COBYLA

# Largest register a single QAOA run simulates. The universe can be any size: a cardinality
# with more eligible assets than this is solved by QAOA in blocks of at most this many assets.
MAX_QUBITS = 10
# Sample cut-off qiskit's MinimumEigenOptimizer applies before picking the best bitstring.
MIN_PROBABILITY = 1e-6
CAP_TOL = 1e-9


def _cardinalities(tickers: list[str], caps: dict[str, float], B: Optional[int]) -> dict[int, list[int]]:
    """Cardinalities to try (only B if given), each mapped to the assets whose cap admits 1/B."""
    n = len(tickers)
    out = {}
    for b in [B] if B is not None else range(1, n + 1):
        if 1 <= b <= n:
            idx = [i for i, t in enumerate(tickers) if 1.0 / b <= caps[t] + CAP_TOL]
            if len(idx) >= b:
                out[b] = idx
    return out


def _qubo(lin: np.ndarray, quad: np.ndarray, b: int, penalty: Optional[float]) -> Tuple[np.ndarray, np.ndarray]:
    """Minimisation QUBO for: maximise lin.x + x.quad.x subject to sum(x) = b.

    Equals qiskit_optimization's QuadraticProgramToQubo with the same penalty, up to a positive
    scale and a constant (a test checks this). Two documented choices:
    - penalty defaults to 2x the objective's span. qiskit's automatic penalty is 1 + span,
      which with daily covariances (~1e-4) is ~1000x the objective, so QAOA would only learn
      "pick b assets", not which ones.
    - the QUBO is divided by its largest coefficient, a positive rescaling with the same
      minimiser, so QAOA's angles act on O(1) energies.
    Returns (linear, upper-triangular quadratic) coefficients.
    """
    k = len(lin)
    quad = np.triu(quad) + np.triu(quad.T, 1)       # fold onto the upper triangle, as qiskit does
    if penalty is None:
        penalty = 2.0 * (np.abs(lin).sum() + np.abs(quad).sum()) or 1.0
    # -objective + penalty * (sum(x) - b)^2, using x_i^2 = x_i and dropping the constant.
    L = -lin + penalty * (1 - 2 * b)
    Q = -quad + 2 * penalty * np.triu(np.ones((k, k)), 1)
    scale = max(np.abs(L).max(), np.abs(Q).max()) or 1.0
    return L / scale, Q / scale


def _qaoa_circuit(energy: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    """Exact simulator of the QAOA circuit whose cost layer has these basis-state energies.

    Returns angles -> output distribution, with angles = (gamma_1..gamma_p, beta_1..beta_p).
    The circuit is |+>^k, then per layer the cost e^{-i gamma E} and the mixer
    e^{-i beta sum X}, i.e. RX(2 beta) on every qubit: qiskit's QAOAAnsatz up to a global
    phase, which a test checks on Aer. Basis state i has qubit j = bit j of i.
    """
    k = energy.size.bit_length() - 1
    halves = (k - k // 2, k // 2)   # mixer = RX on the high half (x) RX on the low half
    # RX(2 beta) on m qubits, entry (i, j) = cos(beta)^(m - d) (-i sin(beta))^d, where
    # d = number of bits in which i and j differ; d is fixed, so compute it once.
    flips = []
    for m in halves:
        diff = np.arange(2**m)[:, None] ^ np.arange(2**m)
        flips.append(((diff[..., None] >> np.arange(m)) & 1).sum(axis=-1))

    def rx(beta: float, m: int, d: np.ndarray) -> np.ndarray:
        j = np.arange(m + 1)
        return (np.cos(beta) ** (m - j) * (-1j * np.sin(beta)) ** j)[d]

    def probabilities(angles: np.ndarray) -> np.ndarray:
        reps = len(angles) // 2
        psi = np.full(energy.size, 2 ** (-k / 2), dtype=complex)
        for gamma, beta in zip(angles[:reps], angles[reps:]):
            psi = psi * np.exp(-1j * gamma * energy)
            high, low = (rx(beta, m, d) for m, d in zip(halves, flips))
            psi = (high @ psi.reshape(2 ** halves[0], 2 ** halves[1]) @ low).reshape(-1)
        return np.abs(psi) ** 2

    return probabilities


def _qaoa_select(
    lin: np.ndarray, quad: np.ndarray, b: int, penalty: Optional[float], reps: int, maxiter: int
) -> Tuple[Optional[np.ndarray], Optional[float]]:
    """One QAOA run on len(lin) qubits: maximise lin.x + x.quad.x subject to sum(x) = b.

    COBYLA tunes the angles against the expected energy. Returns the best feasible bitstring
    the optimised circuit samples, as MinimumEigenOptimizer does, and its probability;
    (None, None) if it samples no feasible bitstring.
    """
    k = len(lin)
    L, Q = _qubo(lin, quad, b, penalty)
    states = ((np.arange(2**k)[:, None] >> np.arange(k)) & 1).astype(np.int8)
    energy = states @ L + ((states @ Q) * states).sum(axis=1)

    probabilities = _qaoa_circuit(energy)
    angles = COBYLA(maxiter=maxiter).minimize(
        lambda a: float(probabilities(a) @ energy), x0=np.full(2 * reps, np.pi / 4)
    ).x
    probs = probabilities(angles)
    sampled = (states.sum(axis=1) == b) & (probs >= MIN_PROBABILITY)
    if not sampled.any():
        return None, None
    i = np.flatnonzero(sampled)[np.argmin(energy[sampled])]
    return states[i].astype(int), float(probs[i])


def _value(lin: np.ndarray, quad: np.ndarray, x: np.ndarray) -> float:
    return float(lin @ x + x @ quad @ x)


def _greedy(lin: np.ndarray, quad: np.ndarray, b: int) -> np.ndarray:
    """Pick b assets one at a time, each with the best marginal gain (block search's start)."""
    x = np.zeros(len(lin), dtype=int)
    gain = lin + np.diag(quad)
    for _ in range(b):
        i = int(np.argmax(np.where(x == 1, -np.inf, gain)))
        x[i] = 1
        gain = gain + 2 * quad[:, i]
    return x


def _block_search(
    lin: np.ndarray, quad: np.ndarray, b: int, max_qubits: int,
    penalty: Optional[float], reps: int, maxiter: int,
) -> Tuple[np.ndarray, int, int]:
    """Cardinality-b selection over more assets than max_qubits, solved by QAOA in blocks.

    Starting from a greedy pick, QAOA re-solves a block of held + unheld assets while the
    rest stay fixed, keeping any improvement. Each pass pairs every chunk of held assets
    with every chunk of unheld ones, and the search ends after a pass with no improvement,
    so no single swap (or any move inside a block) can improve the result.
    Returns (selection, QAOA runs, widest block).
    """
    x = _greedy(lin, quad, b)
    runs, widest, improved = 0, 0, True
    while improved:
        improved = False
        held, unheld = np.flatnonzero(x == 1), np.flatnonzero(x == 0)
        n_held = min(len(held), max_qubits // 2)
        n_unheld = min(len(unheld), max_qubits - n_held)
        n_held = min(len(held), max_qubits - n_unheld)
        for h in np.array_split(held, -(-len(held) // n_held)):
            for u in np.array_split(unheld, -(-len(unheld) // n_unheld)):
                block = np.concatenate([h, u])
                b_block = int(x[block].sum())   # earlier blocks this pass may have moved assets
                if not 0 < b_block < len(block):
                    continue
                fixed = np.setdiff1d(np.flatnonzero(x == 1), block)
                block_lin = lin[block] + 2 * quad[np.ix_(block, fixed)].sum(axis=1)
                xb, _ = _qaoa_select(block_lin, quad[np.ix_(block, block)], b_block, penalty, reps, maxiter)
                runs, widest = runs + 1, max(widest, len(block))
                if xb is None:
                    continue
                candidate = x.copy()
                candidate[block] = xb
                current = _value(lin, quad, x)
                if _value(lin, quad, candidate) > current + 1e-12 * abs(current):
                    x, improved = candidate, True
    return x, runs, widest


def solve_qaoa(
    tickers: list[str],
    mu_hat: list[float],
    sigma: list[list[float]],
    risk_aversion: float,
    caps: dict[str, float],
    long_only: bool = True,         # binary selection is long-only by construction
    B: Optional[int] = None,        # cardinality; None sweeps every B the caps allow
    penalty: Optional[float] = None,
    reps: int = 1,
    maxiter: int = 100,
    max_qubits: int = MAX_QUBITS,
) -> Tuple[dict[str, float], float, float, str, dict]:
    """Equal-weight QAOA portfolio for any number of assets.

    For each cardinality B, QAOA selects exactly B assets held at 1/B; assets whose cap is
    below 1/B are left out. If the rest fit in max_qubits, one QAOA run covers them all
    (and finds the best subset); otherwise QAOA solves them in blocks (see _block_search).
    The B with the best Markowitz objective wins, so the number of holdings comes from the
    data, and no simulated register exceeds max_qubits whatever the universe size.

    Returns (weights, objective_value, solve_time_ms, solver_status, metadata).
    """
    if max_qubits < 2:
        raise ValueError("max_qubits must be at least 2")
    n = len(tickers)
    mu = np.array(mu_hat, dtype=float)
    S = np.array(sigma, dtype=float)
    eligible = _cardinalities(tickers, caps, B)

    start = time.perf_counter()
    best_w, best_obj, best_b, p_solution = np.zeros(n), -np.inf, None, None
    objective_by_B, block_search_B, n_qubits, runs = {}, [], 0, 0
    for b, idx in eligible.items():
        lin = mu[idx] / b                                   # Markowitz objective at w = x/b
        quad = -risk_aversion * S[np.ix_(idx, idx)] / b**2
        p = None
        if len(idx) == b:            # only one subset fits: hold all of it
            x = np.ones(b, dtype=int)
        elif len(idx) <= max_qubits:
            x, p = _qaoa_select(lin, quad, b, penalty, reps, maxiter)
            runs, n_qubits = runs + 1, max(n_qubits, len(idx))
            if x is None:
                continue
        else:
            x, b_runs, widest = _block_search(lin, quad, b, max_qubits, penalty, reps, maxiter)
            runs, n_qubits = runs + b_runs, max(n_qubits, widest)
            block_search_B.append(b)

        w = np.zeros(n)
        w[np.array(idx)[x == 1]] = 1.0 / b
        obj = float(mu @ w - risk_aversion * (w @ S @ w))
        objective_by_B[b] = obj
        if obj > best_obj:
            best_w, best_obj, best_b, p_solution = w, obj, b, p
    solve_time_ms = (time.perf_counter() - start) * 1000.0

    if best_b is None:
        weights = {t: 0.0 for t in tickers}
        obj, status = 0.0, "infeasible"
    else:
        weights = {t: float(best_w[i]) for i, t in enumerate(tickers)}
        obj = best_obj
        # A cardinality whose QAOA run sampled no feasible bitstring leaves the sweep incomplete.
        status = "optimal" if len(objective_by_B) == len(eligible) else "optimal_inaccurate"

    metadata = {
        "n_layers": reps,
        "optimizer": "COBYLA",
        "B": best_b,                          # chosen cardinality
        "B_candidates": list(eligible),       # cardinalities the caps allow
        "objective_by_B": objective_by_B,
        "block_search_B": block_search_B,     # cardinalities solved in blocks
        "max_qubits": max_qubits,
        "n_qubits": n_qubits,                 # widest register actually simulated
        "qaoa_runs": runs,
        "p_solution": p_solution,             # QAOA's probability of the returned bitstring
    }
    return weights, obj, solve_time_ms, status, metadata


def brute_force_solver(
    tickers: list[str],
    mu_hat: list[float],
    sigma: list[list[float]],
    risk_aversion: float,
    caps: dict[str, float],
    B: Optional[int] = None,
) -> Tuple[dict[str, float], float]:
    """Exact baseline for solve_qaoa: enumerate every cap-feasible equal-weight subset.

    Returns (weights, objective_value); all-zero weights if no cardinality is feasible.
    """
    n = len(tickers)
    mu = np.array(mu_hat, dtype=float)
    S = np.array(sigma, dtype=float)
    best_w, best_obj = None, -np.inf
    for b, idx in _cardinalities(tickers, caps, B).items():
        for subset in itertools.combinations(idx, b):
            w = np.zeros(n)
            w[list(subset)] = 1.0 / b
            obj = float(mu @ w - risk_aversion * (w @ S @ w))
            if obj > best_obj:
                best_w, best_obj = w, obj
    if best_w is None:
        return {t: 0.0 for t in tickers}, 0.0
    return {t: float(best_w[i]) for i, t in enumerate(tickers)}, best_obj
