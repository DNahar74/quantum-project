import { useState, useEffect, useMemo } from 'react';
import { fetchResults } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';
import type { RunRow } from '../../lib/types/api';

export const useDrawdownData = (from?: string | null, to?: string | null) => {
  const [rawData, setRawData] = useState<RunRow[]>([]);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!from || !to) return;
    
    let mounted = true;
    setStatus('loading');
    
    fetchResults(undefined, from, to)
      .then(res => {
        if (!mounted) return;
        setRawData(res);
        setStatus('success');
      })
      .catch(err => {
        if (!mounted) return;
        setError(err);
        setStatus('error');
      });
      
    return () => { mounted = false; };
  }, [from, to]);

  const data = useMemo(() => {
    if (rawData.length === 0) return [];
    
    const byDate: Record<string, any> = {};
    rawData.forEach(row => {
      if (!byDate[row.rebalance_date]) {
        byDate[row.rebalance_date] = { date: row.rebalance_date };
      }
      byDate[row.rebalance_date][row.arm_name] = row.realized_return;
    });
    
    const sortedDates = Object.keys(byDate).sort();
    const cum = { markowitz: 1, qaoa: 1 };
    const max = { markowitz: 1, qaoa: 1 };
    
    return sortedDates.map(date => {
      const point = byDate[date];
      if (point.markowitz !== undefined) cum.markowitz *= (1 + point.markowitz);
      if (point.qaoa !== undefined) cum.qaoa *= (1 + point.qaoa);
      
      if (cum.markowitz > max.markowitz) max.markowitz = cum.markowitz;
      if (cum.qaoa > max.qaoa) max.qaoa = cum.qaoa;
      
      return {
        date,
        markowitz: (cum.markowitz - max.markowitz) / max.markowitz,
        qaoa: (cum.qaoa - max.qaoa) / max.qaoa
      };
    });
  }, [rawData]);

  return { data, status, error };
};
