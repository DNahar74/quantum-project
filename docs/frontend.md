# Frontend Dashboard & Graph Definitions

The frontend is a single-page application built with **React**, **TypeScript**, **Vite**, **Tailwind CSS v4**, and **Recharts**. It is entirely decoupled from the business logic and solvers, acting purely as a visualization layer for the immutable `results.db`.

## Deep Dive: What Each Graph Represents

The dashboard visualizes the comparative performance of the Markowitz and QAOA solvers across several key dimensions.

### 1. Comparison Overview (Grouped Bar Chart)
**What it represents:** A high-level aggregate summary of the entire backtest duration. It answers the fundamental question: *Which solver strategy performed better overall?*

**Metrics displayed per arm:**
*   **Annualized Return**: The geometric average amount of money earned by the portfolio each year over the given time period. Higher is better.
*   **Max Drawdown**: The maximum observed loss from a peak to a trough of a portfolio, before a new peak is attained. It measures extreme downside risk. Lower (closer to 0) is better.
*   **Avg Turnover**: The average percentage of the portfolio's value that was traded/rebalanced each week. High turnover incurs high transaction costs. Lower is generally better.
*   **Avg Solve Time**: The mean latency (in milliseconds) the solver took to compute the weights.

### 2. Cumulative Returns (Multi-Line Chart)
**What it represents:** The compounded growth of a hypothetical $1.00 investment starting at the beginning of the backtest. 

**How to read it:**
*   The Y-axis represents the portfolio's multiplier value (e.g., 1.05 means a 5% gain from inception).
*   The X-axis represents time (Rebalance Dates).
*   If the QAOA line sits consistently above the Markowitz line, the QAOA cardinality-constrained strategy generated more total wealth.
*   Dips in the line represent periods of negative market performance.

### 3. Allocation Over Time (Stacked Area Chart)
**What it represents:** The exact asset weights (percentages) chosen by a specific solver at every rebalance date. 

**How to read it:**
*   You must select a specific "Arm" (e.g., `markowitz` or `qaoa-exact`) to view its allocation.
*   The Y-axis goes from 0 to 1 (0% to 100% of the portfolio).
*   The colored "bands" represent different assets (e.g., specific industries like `Manuf` or `Enrgy`). The thickness of a band at any given date is the percentage of the portfolio allocated to that asset.
*   **Markowitz** usually displays many thin, continuous bands because it can assign fractional weights (e.g., 2.3% to Health, 14.1% to Energy).
*   **QAOA** (with cardinality $B=5$) will display exactly 5 thick bands of equal width ($20\%$ each), representing the discrete binary selection of the QUBO solver.

### 4. Drawdown (Shaded Area Chart)
**What it represents:** The percentage drop in the portfolio's value from its historical peak at any given point in time. It visualizes the "pain" an investor would feel holding the portfolio.

**How to read it:**
*   The Y-axis is negative (e.g., 0% down to -20%).
*   When the chart is at 0%, the portfolio is at an all-time high (a "high-water mark").
*   Deep, wide shaded areas indicate severe, long-lasting losses.
*   Comparing the drawdowns of Markowitz vs QAOA reveals which strategy is more robust during market crashes.

### 5. Run History (Data Table)
**What it represents:** The raw, tabular audit trail of the backtest.
*   Displays the exact Solve Time (ms) per rebalance.
*   Displays the `solver_status` (e.g., `optimal`, `infeasible`). A red indicator flag is shown on the charts if a solver failed to find an optimal solution.
*   Displays the `sigma_hash` and `caps_hash`. You can visually verify that both the Markowitz row and the QAOA row for the same date possess the exact same hash, proving they received identical inputs.
