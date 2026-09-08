import { useState, useEffect, useMemo } from 'react';
import { fetchResults } from '../../lib/api/results';
import type { FetchStatus } from '../../lib/hooks/useRuns';
import type { RunRow } from '../../lib/types/api';

export interface RunHistoryItem {
  request_id: string;
  date: string;
  arms: string;
  status: string;
  hasError: boolean;
}

export const useRunHistoryData = () => {
  const [rawData, setRawData] = useState<RunRow[]>([]);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;
    setStatus('loading');
    
    fetchResults()
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
  }, []);

  const data = useMemo<RunHistoryItem[]>(() => {
    if (rawData.length === 0) return [];
    
    const uniqueRuns: Record<string, any> = {};
    rawData.forEach(row => {
      if (!uniqueRuns[row.request_id]) {
        uniqueRuns[row.request_id] = {
          request_id: row.request_id,
          date: row.rebalance_date,
          arms: new Set<string>(),
          status: new Set<string>()
        };
      }
      uniqueRuns[row.request_id].arms.add(row.arm_name);
      uniqueRuns[row.request_id].status.add(row.solver_status);
    });
    
    const arr = Object.values(uniqueRuns).map(r => ({
      ...r,
      arms: Array.from(r.arms).join(', '),
      status: Array.from(r.status).join(', '),
      hasError: Array.from(r.status).some((s: any) => s !== 'optimal')
    }));
    
    arr.sort((a, b) => b.date.localeCompare(a.date));
    return arr;
  }, [rawData]);

  return { data, status, error };
};
