import { useState, useEffect } from 'react';
import { fetchResults } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';
import type { RunRow } from '../../lib/types/api';

export const ARMS = ['markowitz', 'qaoa'] as const;
export type Arm = typeof ARMS[number];

/**
 * Loads every rebalance for both arms once; windowing and aggregation happen client-side,
 * so changing the window is instant. Assets are in returns-file order (the order the
 * orchestrator stores weights in), which fixes stacking order and colors.
 */
export const useAllocationRows = () => {
  const [rows, setRows] = useState<Record<Arm, RunRow[]>>({ markowitz: [], qaoa: [] });
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;
    setStatus('loading');
    Promise.all(ARMS.map(arm => fetchResults(arm)))
      .then(([markowitz, qaoa]) => {
        if (!mounted) return;
        const byDate = (a: RunRow, b: RunRow) => a.rebalance_date.localeCompare(b.rebalance_date);
        setRows({ markowitz: [...markowitz].sort(byDate), qaoa: [...qaoa].sort(byDate) });
        setStatus('success');
      })
      .catch(err => {
        if (!mounted) return;
        setError(err);
        setStatus('error');
      });
    return () => { mounted = false; };
  }, []);

  const all = [...rows.markowitz, ...rows.qaoa];
  const assets: string[] = [];
  for (const row of all) for (const a of Object.keys(row.weights)) if (!assets.includes(a)) assets.push(a);
  const dates = all.map(r => r.rebalance_date).sort();

  return { rows, assets, minDate: dates[0] ?? null, maxDate: dates[dates.length - 1] ?? null, status, error };
};
