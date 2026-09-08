import { useState, useEffect, useMemo } from 'react';
import { fetchResults } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';
import type { RunRow } from '../../lib/types/api';

export const useAllocationData = (arm: string, from?: string | null, to?: string | null) => {
  const [rawData, setRawData] = useState<RunRow[]>([]);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!from || !to) return;
    
    let mounted = true;
    setStatus('loading');
    
    fetchResults(arm, from, to)
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
  }, [arm, from, to]);

  const data = useMemo(() => {
    if (rawData.length === 0) return [];
    
    return rawData.map(row => ({
      date: row.rebalance_date,
      ...row.weights
    }));
  }, [rawData]);

  return { data, status, error };
};
