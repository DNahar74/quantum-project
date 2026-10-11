import { useState, useEffect } from 'react';
import { fetchRuns } from '../api/results';
import type { RunsResponse } from '../types/api';

export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export const useRuns = () => {
  const [data, setData] = useState<RunsResponse | null>(null);
  const [status, setStatus] = useState<FetchStatus>('idle');
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;
    setStatus('loading');

    fetchRuns()
      .then(res => {
        if (!mounted) return;
        setData(res);
        setStatus('success');
      })
      .catch(err => {
        if (!mounted) return;
        setError(err);
        setStatus('error');
      });

    return () => {
      mounted = false;
    };
  }, []);

  return { data, status, error };
};
