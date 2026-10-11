import type { RunRow } from '../types/api';

export type Bucket = 'week' | 'month' | 'quarter' | 'year';

export const BUCKET_LABEL: Record<Bucket, string> = {
  week: 'weekly',
  month: 'monthly',
  quarter: 'quarterly',
  year: 'yearly',
};

// Weights below this count as "not held" (solver tolerance).
const HELD_THRESHOLD = 0.001;

/** Coarser buckets for longer windows, keeping figures at roughly 40-160 periods. */
export const autoBucket = (from: string, to: string): Bucket => {
  const years = (Date.parse(to) - Date.parse(from)) / (365.25 * 864e5);
  if (years <= 3) return 'week';
  if (years <= 12) return 'month';
  if (years <= 40) return 'quarter';
  return 'year';
};

export const bucketKey = (date: string, bucket: Bucket): string => {
  const [year, month] = date.split('-');
  if (bucket === 'week') return date;
  if (bucket === 'month') return `${year}-${month}`;
  if (bucket === 'quarter') return `${year} Q${Math.floor((Number(month) - 1) / 3) + 1}`;
  return year;
};

const effectiveN = (weights: Record<string, number>): number => {
  const hhi = Object.values(weights).reduce((s, w) => s + w * w, 0);
  return hhi > 0 ? 1 / hhi : 0;
};

const holdings = (weights: Record<string, number>): number =>
  Object.values(weights).filter(w => w > HELD_THRESHOLD).length;

export interface Period {
  label: string;
  start: string;
  end: string;
  nRebalances: number;
  weights: Record<string, number>;   // mean weight per asset over the period's rebalances
  effectiveN: number;                // mean of 1 / sum(w^2) over the period's rebalances
  holdings: number;                  // mean number of assets held
}

/** Averages weekly rows (sorted by date) into periods of the given bucket. */
export const aggregate = (rows: RunRow[], assets: string[], bucket: Bucket): Period[] => {
  const periods: Period[] = [];
  let current: Period | null = null;
  for (const row of rows) {
    const label = bucketKey(row.rebalance_date, bucket);
    if (!current || current.label !== label) {
      current = { label, start: row.rebalance_date, end: row.rebalance_date, nRebalances: 0,
                  weights: Object.fromEntries(assets.map(a => [a, 0])), effectiveN: 0, holdings: 0 };
      periods.push(current);
    }
    current.end = row.rebalance_date;
    current.nRebalances += 1;
    for (const a of assets) current.weights[a] += row.weights[a] ?? 0;
    current.effectiveN += effectiveN(row.weights);
    current.holdings += holdings(row.weights);
  }
  for (const p of periods) {
    for (const a of assets) p.weights[a] /= p.nRebalances;
    p.effectiveN /= p.nRebalances;
    p.holdings /= p.nRebalances;
  }
  return periods;
};

export interface AssetStats {
  asset: string;
  mean: number;
  max: number;
  heldShare: number;  // share of rebalances with a non-zero weight
}

export interface WindowSummary {
  nRebalances: number;
  assets: AssetStats[];
  avgHoldings: number;
  avgEffectiveN: number;
  avgTurnover: number;
}

export const summarize = (rows: RunRow[], assets: string[]): WindowSummary => {
  const n = rows.length || 1;
  const mean = (f: (r: RunRow) => number) => rows.reduce((s, r) => s + f(r), 0) / n;
  return {
    nRebalances: rows.length,
    assets: assets.map(asset => ({
      asset,
      mean: mean(r => r.weights[asset] ?? 0),
      max: rows.reduce((m, r) => Math.max(m, r.weights[asset] ?? 0), 0),
      heldShare: mean(r => ((r.weights[asset] ?? 0) > HELD_THRESHOLD ? 1 : 0)),
    })),
    avgHoldings: mean(r => holdings(r.weights)),
    avgEffectiveN: mean(r => effectiveN(r.weights)),
    avgTurnover: mean(r => r.turnover),
  };
};
