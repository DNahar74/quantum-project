import pytest
import numpy as np
import sys
import os
import unittest.mock as mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from qiskit import transpile
from qiskit.circuit.library import QAOAAnsatz
from qiskit_aer import AerSimulator
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo
from app import solver
from app.solver import solve_qaoa, brute_force_solver, MAX_QUBITS

TICKERS = ["A", "B", "C", "D", "E"]
MU_HAT = [0.1, 0.05, 0.12, 0.08, 0.02]
SIGMA = [
    [0.04, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.01, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.09, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.02, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.03]
]


def universe(n, seed, with_mu=False):
    """Synthetic daily-scale universe of n assets: one market factor plus idiosyncratic risk,
    with caps built the way caps_for_date builds them (inverse vol x 5, clipped at 0.40)."""
    rng = np.random.default_rng(seed)
    beta = rng.uniform(0.6, 1.4, n)
    idio = rng.uniform(0.004, 0.015, n)
    sigma = np.outer(beta, beta) * 0.01**2 + np.diag(idio**2)
    mu = rng.normal(0.0004, 0.0006, n) if with_mu else np.zeros(n)
    inv_vol = 1 / np.sqrt(np.diag(sigma))
    caps = np.clip(inv_vol / inv_vol.sum() * 5.0, None, 0.40)
    tickers = [f"T{i}" for i in range(n)]
    return tickers, mu.tolist(), sigma.tolist(), dict(zip(tickers, caps.tolist()))


def markowitz(mu_hat, sigma, q, w):
    return float(np.dot(mu_hat, w) - q * w @ np.array(sigma) @ w)


def assert_valid_equal_weight(tickers, caps, weights, metadata):
    w = np.array([weights[t] for t in tickers])
    held = w > 0
    assert held.sum() == metadata["B"]
    assert np.allclose(w[held], 1.0 / metadata["B"])
    assert abs(w.sum() - 1.0) < 1e-9
    for t in tickers:
        assert weights[t] <= caps[t] + 1e-9


def assert_swap_optimal(tickers, mu_hat, sigma, q, caps, weights):
    """No swap of a held asset for an eligible unheld one improves the objective."""
    w = np.array([weights[t] for t in tickers])
    b = int(round(1 / w.max()))
    base = markowitz(mu_hat, sigma, q, w)
    eligible = [j for j, t in enumerate(tickers) if 1.0 / b <= caps[t] + 1e-9 and w[j] == 0]
    for i in np.flatnonzero(w):
        for j in eligible:
            v = w.copy()
            v[i], v[j] = 0.0, 1.0 / b
            assert markowitz(mu_hat, sigma, q, v) <= base + 1e-12 * abs(base)


@pytest.mark.parametrize("k,reps", [(1, 1), (3, 1), (5, 2), (6, 3)])
def test_qaoa_simulation_matches_qiskit_aer(k, reps):
    """The solver's statevector is qiskit's QAOAAnsatz circuit as Aer simulates it."""
    rng = np.random.default_rng(k)
    qp = QuadraticProgram()
    for i in range(k):
        qp.binary_var(f"x{i}")
    A = rng.normal(size=(k, k))
    qp.minimize(linear=rng.normal(size=k), quadratic=A + A.T)
    states = (np.arange(2**k)[:, None] >> np.arange(k)) & 1
    energy = np.array([qp.objective.evaluate(x) for x in states])
    gammas, betas = rng.uniform(0, np.pi, reps), rng.uniform(0, np.pi, reps)

    operator, _ = qp.to_ising()
    circuit = QAOAAnsatz(operator, reps=reps)
    circuit.save_probabilities()
    simulator = AerSimulator(method="statevector")
    circuit = transpile(circuit, simulator)
    binds = {p: [(betas if p.vector.name == "β" else gammas)[p.index]] for p in circuit.parameters}
    aer = np.asarray(simulator.run(circuit, parameter_binds=[binds]).result().data(0)["probabilities"])

    assert np.allclose(solver._qaoa_circuit(energy)(np.r_[gammas, betas]), aer, atol=1e-12)


@pytest.mark.parametrize("penalty", [None, 0.7])
def test_qubo_matches_qiskit_converter(penalty):
    """_qubo is qiskit's QuadraticProgramToQubo up to a positive scale and a constant;
    the default penalty is 2x the objective span qiskit computes."""
    rng = np.random.default_rng(0)
    k, b = 6, 2
    lin = rng.normal(size=k)
    A = rng.normal(size=(k, k))
    quad = (A + A.T) / 2
    qp = QuadraticProgram()
    for i in range(k):
        qp.binary_var(f"x{i}")
    qp.maximize(linear=lin, quadratic=quad)
    qp.linear_constraint(linear=np.ones(k), sense="==", rhs=b)
    if penalty is None:
        lin_b, quad_b = qp.objective.linear.bounds, qp.objective.quadratic.bounds
        reference_penalty = 2 * ((lin_b.upperbound - lin_b.lowerbound) + (quad_b.upperbound - quad_b.lowerbound))
    else:
        reference_penalty = penalty
    qubo = QuadraticProgramToQubo(penalty=reference_penalty).convert(qp)

    states = (np.arange(2**k)[:, None] >> np.arange(k)) & 1
    reference = np.array([qubo.objective.evaluate(x) for x in states])
    L, Q = solver._qubo(lin, quad, b, penalty)
    energy = states @ L + ((states @ Q) * states).sum(axis=1)

    slope, intercept = np.polyfit(energy, reference, 1)
    assert slope > 0
    assert np.allclose(slope * energy + intercept, reference)


def test_sweep_matches_brute_force():
    caps = {t: 1.0 for t in TICKERS}

    w_qaoa, obj_qaoa, t_ms, status, metadata = solve_qaoa(TICKERS, MU_HAT, SIGMA, 1.0, caps, True)
    w_exact, obj_exact = brute_force_solver(TICKERS, MU_HAT, SIGMA, 1.0, caps)

    assert status == "optimal"
    assert metadata["B_candidates"] == [1, 2, 3, 4, 5]
    assert metadata["n_qubits"] == len(TICKERS)
    assert metadata["block_search_B"] == []
    assert np.isclose(obj_qaoa, obj_exact, rtol=1e-9, atol=0)
    assert w_qaoa == pytest.approx(w_exact)
    assert_valid_equal_weight(TICKERS, caps, w_qaoa, metadata)
    # Reported objective is the Markowitz objective of the untransformed inputs.
    w = np.array([w_qaoa[t] for t in TICKERS])
    assert np.isclose(obj_qaoa, markowitz(MU_HAT, SIGMA, 1.0, w), rtol=1e-12, atol=0)


def test_cardinality_follows_the_data():
    # Pure minimum variance over independent, equal-volatility assets: holding all of them wins.
    sigma = (0.02 * np.eye(5)).tolist()
    caps = {t: 1.0 for t in TICKERS}

    w_qaoa, _, _, status, metadata = solve_qaoa(TICKERS, [0.0] * 5, sigma, 1.0, caps, True)

    assert status == "optimal"
    assert metadata["B"] == 5
    assert all(np.isclose(w, 0.2) for w in w_qaoa.values())


def test_caps_exclude_assets_per_cardinality():
    # C's cap rules it out at B=3 (1/3 > 0.25) but not at B=4, so B=3 runs on 4 qubits.
    caps = {"A": 0.4, "B": 0.4, "C": 0.25, "D": 0.4, "E": 0.4}

    w_qaoa, obj_qaoa, _, status, metadata = solve_qaoa(TICKERS, MU_HAT, SIGMA, 1.0, caps, True)
    w_exact, obj_exact = brute_force_solver(TICKERS, MU_HAT, SIGMA, 1.0, caps)

    assert status == "optimal"
    assert metadata["B_candidates"] == [3, 4, 5]
    assert np.isclose(obj_qaoa, obj_exact, rtol=1e-9, atol=0)
    assert w_qaoa == pytest.approx(w_exact)
    assert_valid_equal_weight(TICKERS, caps, w_qaoa, metadata)


def test_caps_too_tight_is_infeasible():
    # Even five assets at 1/5 = 0.2 exceed a 0.15 cap.
    caps = {t: 0.15 for t in TICKERS}

    w_qaoa, obj_qaoa, _, status, metadata = solve_qaoa(TICKERS, MU_HAT, SIGMA, 1.0, caps, True)

    assert status == "infeasible"
    assert metadata["B_candidates"] == []
    assert all(w == 0.0 for w in w_qaoa.values())
    assert obj_qaoa == 0.0


def test_untransformed_inputs():
    """
    Confirm that this service's copy of mu_hat/sigma/risk_aversion is never
    transformed before use in the objective: the QUBO is built from the Markowitz
    objective at w = x/B.
    """
    tickers = ["A", "B", "C"]
    mu_hat = [0.1, 0.2, 0.3]
    sigma = [
        [0.1, 0.02, 0.0],
        [0.02, 0.1, 0.0],
        [0.0, 0.0, 0.1]
    ]
    q = 2.0
    B = 2
    caps = {t: 0.5 for t in tickers}

    calls = []
    original_qubo = solver._qubo

    def recording_qubo(lin, quad, b, penalty):
        calls.append((lin, quad, b))
        return original_qubo(lin, quad, b, penalty)

    with mock.patch.object(solver, "_qubo", recording_qubo):
        solve_qaoa(tickers, mu_hat, sigma, q, caps, True, B=B)

    lin, quad, b = calls[0]
    assert b == B
    assert np.allclose(lin, np.array(mu_hat) / B)
    assert np.allclose(quad, -q * np.array(sigma) / B**2)


@pytest.mark.parametrize("n", [3, 5, 8, 12, 17, 30, 49])
def test_any_universe_size(n):
    tickers, mu_hat, sigma, caps = universe(n, seed=n)

    weights, obj, _, status, metadata = solve_qaoa(tickers, mu_hat, sigma, 1.0, caps, True)

    assert status == "optimal"
    assert metadata["B"] in metadata["B_candidates"]
    assert metadata["n_qubits"] <= MAX_QUBITS
    assert bool(metadata["block_search_B"]) == (n > MAX_QUBITS)
    assert_valid_equal_weight(tickers, caps, weights, metadata)
    assert_swap_optimal(tickers, mu_hat, sigma, 1.0, caps, weights)
    if n <= 17:  # small enough to enumerate every subset
        assert np.isclose(obj, brute_force_solver(tickers, mu_hat, sigma, 1.0, caps)[1], rtol=1e-9, atol=0)


@pytest.mark.parametrize("n,max_qubits,with_mu", [(11, 6, False), (13, 6, True), (15, 8, False), (15, 4, True)])
def test_block_search_matches_brute_force(n, max_qubits, with_mu):
    tickers, mu_hat, sigma, caps = universe(n, seed=100 + n, with_mu=with_mu)

    weights, obj, _, status, metadata = solve_qaoa(
        tickers, mu_hat, sigma, 1.0, caps, True, max_qubits=max_qubits
    )
    w_exact, obj_exact = brute_force_solver(tickers, mu_hat, sigma, 1.0, caps)

    assert status == "optimal"
    assert metadata["block_search_B"]
    assert metadata["n_qubits"] <= max_qubits
    assert np.isclose(obj, obj_exact, rtol=1e-9, atol=0)


@pytest.mark.parametrize("max_qubits", [2, 3, 7])
def test_register_never_exceeds_max_qubits(max_qubits):
    tickers, mu_hat, sigma, caps = universe(20, seed=7, with_mu=True)

    weights, _, _, status, metadata = solve_qaoa(
        tickers, mu_hat, sigma, 1.0, caps, True, max_qubits=max_qubits
    )

    assert status == "optimal"
    assert 0 < metadata["n_qubits"] <= max_qubits
    assert_valid_equal_weight(tickers, caps, weights, metadata)
    assert_swap_optimal(tickers, mu_hat, sigma, 1.0, caps, weights)


def test_one_and_two_assets():
    w, _, _, status, metadata = solve_qaoa(["A"], [0.01], [[0.04]], 1.0, {"A": 1.0}, True)
    assert status == "optimal"
    assert w == {"A": 1.0}

    tickers, sigma, caps = ["A", "B"], [[0.04, 0.0], [0.0, 0.01]], {"A": 1.0, "B": 1.0}
    w, obj, _, status, metadata = solve_qaoa(tickers, [0.0, 0.0], sigma, 1.0, caps, True)
    assert status == "optimal"
    assert metadata["B_candidates"] == [1, 2]
    assert np.isclose(obj, brute_force_solver(tickers, [0.0, 0.0], sigma, 1.0, caps)[1], rtol=1e-9, atol=0)


def test_same_inputs_same_portfolio():
    tickers, mu_hat, sigma, caps = universe(17, seed=3, with_mu=True)

    first = solve_qaoa(tickers, mu_hat, sigma, 1.0, caps, True)
    second = solve_qaoa(tickers, mu_hat, sigma, 1.0, caps, True)

    assert first[0] == second[0]
    assert first[4]["objective_by_B"] == second[4]["objective_by_B"]


def test_max_qubits_below_two_rejected():
    with pytest.raises(ValueError, match="max_qubits"):
        solve_qaoa(TICKERS, MU_HAT, SIGMA, 1.0, {t: 1.0 for t in TICKERS}, True, max_qubits=1)
