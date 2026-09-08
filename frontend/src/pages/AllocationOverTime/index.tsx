import React, { useState } from 'react';
import { useAllocationData } from './AllocationOverTime.hooks';
import { useRuns } from '../../lib/hooks/useRuns';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { StackedAreaChart } from '../../components/charts/StackedAreaChart';
import { formatPercent } from '../../lib/utils/format';
import { CHART_DIMENSIONS } from '../../lib/theme/chartTheme';

const AllocationOverTime: React.FC = () => {
  const [selectedArm, setSelectedArm] = useState('markowitz');
  const { data: runData } = useRuns();
  const { data, status, error } = useAllocationData(selectedArm, runData?.start_date, runData?.end_date);

  if (status === 'loading') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (!runData?.start_date || (status === 'success' && data.length === 0)) {
    return <EmptyState message="No runs in this date range" />;
  }

  const areas = data.length > 0 ? Object.keys(data[0]).filter(k => k !== 'date') : [];

  const ArmSelector = (
    <select 
      className="px-4 py-2 border border-slate-200 rounded-lg shadow-sm bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-slate-400"
      value={selectedArm}
      onChange={e => setSelectedArm(e.target.value)}
    >
      <option value="markowitz">Markowitz</option>
      <option value="qaoa">QAOA</option>
    </select>
  );

  return (
    <div className="space-y-6 flex flex-col h-full">
      <PageHeader 
        title="Allocation Over Time" 
        description="Asset weight shifts across rebalance dates" 
      >
        {ArmSelector}
      </PageHeader>

      <Card title="Portfolio Composition" className="flex-grow">
        <div style={{ height: CHART_DIMENSIONS.height }}>
          <StackedAreaChart 
            data={data} 
            xKey="date" 
            areas={areas} 
            tickFormatter={(val: number) => formatPercent(val, 0)}
            tooltipFormatter={(val: number) => formatPercent(val)} 
          />
        </div>
      </Card>
    </div>
  );
};

export default AllocationOverTime;
