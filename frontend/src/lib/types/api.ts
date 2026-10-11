export interface RunRow {
  id?: number;
  request_id: string;
  rebalance_date: string;
  arm_name: string;
  solver_status: string;
  solver_name: string;
  solve_time_ms: number;
  objective_value: number;
  realized_return: number;
  turnover: number;
  weights: Record<string, number>;
  risk_aversion?: number;
  transaction_cost?: number;
}

export interface ComparisonMetrics {
  annualized_sharpe: number;
  max_drawdown: number;
  avg_turnover: number;
}

export type ComparisonResponse = Record<string, ComparisonMetrics>;

export interface RunsResponse {
  start_date: string | null;
  end_date: string | null;
  total_requests: number;
}
