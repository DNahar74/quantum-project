import axios from 'axios';
import type { RunRow, ComparisonResponse, RunsResponse } from '../types/api';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8002';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

export const fetchRuns = async (): Promise<RunsResponse> => {
  const response = await api.get<RunsResponse>('/runs');
  return response.data;
};

export const fetchResults = async (
  arm?: string,
  from?: string | null,
  to?: string | null
): Promise<RunRow[]> => {
  const params: Record<string, string> = {};
  if (arm) params.arm = arm;
  if (from) params.from_date = from;
  if (to) params.to_date = to;

  const response = await api.get<RunRow[]>('/results', { params });
  return response.data;
};

export const fetchComparison = async (
  from?: string | null,
  to?: string | null
): Promise<ComparisonResponse> => {
  const params: Record<string, string> = {};
  if (from) params.from_date = from;
  if (to) params.to_date = to;

  const response = await api.get<ComparisonResponse>('/comparison', { params });
  return response.data;
};
