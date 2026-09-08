import React from 'react';
import { Link } from 'react-router-dom';
import { useRunHistoryData } from './RunHistory.hooks';
import type { RunHistoryItem } from './RunHistory.hooks';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { Table } from '../../components/ui/Table';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';

const RunHistory: React.FC = () => {
  const { data, status, error } = useRunHistoryData();

  if (status === 'loading') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (status === 'success' && data.length === 0) {
    return <EmptyState message="No run history available" />;
  }

  const columns = [
    { header: 'Date', accessor: (row: RunHistoryItem) => row.date },
    { header: 'Request ID', accessor: (row: RunHistoryItem) => <span className="font-mono text-xs">{row.request_id}</span> },
    { header: 'Arms', accessor: (row: RunHistoryItem) => <span className="capitalize">{row.arms}</span> },
    { 
      header: 'Status', 
      accessor: (row: RunHistoryItem) => (
        <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
          row.hasError ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'
        }`}>
          {row.status}
        </span>
      ) 
    },
    { 
      header: 'Actions', 
      accessor: () => (
        <Link to="/" className="text-blue-600 hover:text-blue-900 font-medium transition-colors">
          View Charts
        </Link>
      ) 
    }
  ];

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Run History" 
        description="Detailed log of all optimization requests and solver statuses" 
      />

      <Card title="All Recorded Rebalances" className="!p-0 overflow-hidden border-0">
        <Table data={data} columns={columns} keyExtractor={(row) => row.request_id} />
      </Card>
    </div>
  );
};

export default RunHistory;
