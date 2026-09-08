# Solver Services: Mathematical Formulation & Steps

Both solvers are stateless FastAPI microservices. They expose a `/optimize` endpoint that accepts an `OptimizationRequest` (containing expected returns $\hat{\mu}$, covariance matrix $\Sigma$, and asset caps) and returns an `OptimizationResult` containing the optimal portfolio weights $w$.

---

## 1. Markowitz Service (Continuous QP)
This service implements the classic Modern Portfolio Theory (MPT) Mean-Variance optimization. It aims to maximize expected returns while heavily penalizing variance (risk).

### Variables and Parameters
*   $N$: Number of assets in the universe.
*   $w \in \mathbb{R}^N$: The decision variable vector representing the fractional weight allocated to each asset. Continuous between 0 and 1.
*   $\hat{\mu} \in \mathbb{R}^N$: The vector of expected returns for each asset.
*   $\Sigma \in \mathbb{R}^{N \times N}$: The covariance matrix representing the variance of each asset and the correlation between them.
*   $q$: The risk aversion parameter. Higher $q$ heavily penalizes volatility, pushing the solver toward lower-risk assets.
*   $caps \in \mathbb{R}^N$: The maximum allowable weight for each asset (to prevent over-concentration).

### Objective Function
Maximize the risk-adjusted return:
$$ \max_w \; \hat{\mu}^\top w - q\, w^\top \Sigma w $$

### Constraints
1.  **Fully Invested**: $\sum_i w_i = 1$ (100% of capital is deployed).
2.  **Long-Only**: $w_i \ge 0$ (No short selling).
3.  **Caps**: $w_i \le \text{caps}_i$ (No asset exceeds its dynamic cap).

### Optimizer Steps (CVXPY / OSQP)
1.  **Input Parsing**: Extracts $\hat{\mu}$, $\Sigma$, caps, and $q$ from the JSON request.
2.  **PSD Correction**: Computes the eigenvalues of $\Sigma$. If $\Sigma$ is not perfectly Positive Semi-Definite (due to numerical precision or $N > T$ issues), it projects $\Sigma$ to the nearest PSD matrix by clipping negative eigenvalues to a small epsilon. This is strictly required by the OSQP backend.
3.  **Variable Definition**: Initializes a `cvxpy.Variable(N)` representing $w$.
4.  **Problem Assembly**: Constructs the objective function and appends the 3 constraints.
5.  **Execution**: Calls `prob.solve(solver=cp.OSQP)`.
6.  **Extraction**: Pulls the optimal $w$ vector, formats it into a dictionary mapping asset tickers to float weights, and returns it.

---

## 2. QAOA Service (Combinatorial QUBO)
This service reformulates portfolio selection as a Quadratic Unconstrained Binary Optimization (QUBO) problem. Instead of fractional weights, the quantum algorithm must make a binary "Yes/No" decision for every asset to hit a strict cardinality target $B$.

### Variables and Parameters
*   $x \in \{0, 1\}^N$: The binary decision variable vector. $x_i = 1$ if asset $i$ is selected, $0$ otherwise.
*   $B$: The cardinality target (e.g., select exactly 5 assets from the 12 available).
*   $\lambda$: A massive penalty multiplier used to enforce the cardinality constraint softly within the QUBO objective.

### Objective Function (QUBO)
Maximize the discrete risk-adjusted return while penalizing deviations from $B$:
$$ \max_x \sum_i \hat{\mu}_i x_i - q\sum_{i,j}\sigma_{ij}x_i x_j - \lambda\Big(B-\sum_i x_i\Big)^2 $$

Once the optimal binary string $x$ is found, the final portfolio weights are assigned equally:
$$ w_i = \frac{x_i}{B} $$

### Optimizer Steps (Qiskit QAOA / Exact Solver)
1.  **QUBO Construction**: The service uses `qiskit_optimization` to map the objective function into an Ising Hamiltonian (a matrix of Pauli Z operators representing the qubits' energy landscape).
2.  **Solver Routing**:
    *   **Exact Brute Force**: Used as a baseline. It iterates through all $2^N$ possible bitstrings (or specifically $C(N, B)$ subsets) and evaluates the QUBO cost function to find the absolute global minimum energy state.
    *   **QAOA (Quantum)**: Uses the Quantum Approximate Optimization Algorithm.
3.  **QAOA Circuit Generation**: 
    *   Applies a layer of Hadamard gates to create a uniform superposition of all $2^N$ possible portfolios.
    *   Alternates between applying the Phase Separator operator $e^{-i \gamma H_C}$ (based on the QUBO matrix) and the Mixer operator $e^{-i \beta H_M}$ (to cause quantum interference).
4.  **Simulation & Optimization**: The classical optimizer (COBYLA) tweaks the angles $\gamma$ and $\beta$, simulates the quantum circuit using `qiskit-aer`, and measures the output distribution. It loops this until the angles produce a high probability of measuring the optimal bitstring.
5.  **Extraction**: The most probable bitstring is extracted, mapped to $1/B$ equal weights, and returned.
