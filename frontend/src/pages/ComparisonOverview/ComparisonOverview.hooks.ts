import { useState, useEffect } from 'react';
import { fetchComparison } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';

export const useComparisonData = (from?: string | null, to?: string | null) => {
  const [data, setData] = useState<any[]>([]);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!from || !to) return;
    
    let mounted = true;
    setStatus('loading');
    
    fetchComparison(from, to)
      .then(res => {
        if (!mounted) return;
        const formatted = Object.keys(res).map(arm => ({
          name: arm,
          Sharpe: res[arm].annualized_sharpe,
          MaxDrawdown: res[arm].max_drawdown,
          AvgTurnover: res[arm].avg_turnover
        }));
        setData(formatted);
        setStatus('success');
      })
      .catch(err => {
        if (!mounted) return;
        setError(err);
        setStatus('error');
      });
      
    return () => { mounted = false; };
  }, [from, to]);

  return { data, status, error };
};
