import { useState, useEffect, useMemo } from 'react';
import { fetchResults } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';
import type { RunRow } from '../../lib/types/api';

export const useCumulativeReturnsData = (from?: string | null, to?: string | null) => {
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
        byDate[row.rebalance_date] = { date: row.rebalance_date, inaccuratePoints: [] };
      }
      byDate[row.rebalance_date][row.arm_name] = row.realized_return;
      if (row.solver_status !== 'optimal') {
        byDate[row.rebalance_date].inaccuratePoints.push(row.arm_name);
      }
    });
    
    const sortedDates = Object.keys(byDate).sort();
    const cum = { markowitz: 1, qaoa: 1 };
    
    return sortedDates.map(date => {
      const point = byDate[date];
      if (point.markowitz !== undefined) cum.markowitz *= (1 + point.markowitz);
      if (point.qaoa !== undefined) cum.qaoa *= (1 + point.qaoa);
      
      return {
        date,
        markowitz: cum.markowitz - 1,
        qaoa: cum.qaoa - 1,
        hasInaccurate: point.inaccuratePoints.length > 0
      };
    });
  }, [rawData]);

  return { data, status, error };
};
