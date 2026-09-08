import React from 'react';
import { useCumulativeReturnsData } from './CumulativeReturns.hooks';
import { useRuns } from '../../lib/hooks/useRuns';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { MultiLineChart } from '../../components/charts/MultiLineChart';
import { ArmLegend } from '../../components/ui/ArmLegend';
import { formatPercent } from '../../lib/utils/format';
import { CHART_DIMENSIONS } from '../../lib/theme/chartTheme';

const CumulativeReturns: React.FC = () => {
  const { data: runData } = useRuns();
  const { data, status, error } = useCumulativeReturnsData(runData?.start_date, runData?.end_date);

  if (status === 'loading') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (!runData?.start_date || (status === 'success' && data.length === 0)) {
    return <EmptyState message="No runs in this date range" />;
  }

  const lines = ['markowitz', 'qaoa'];

  return (
    <div className="space-y-6 flex flex-col h-full">
      <PageHeader 
        title="Cumulative Returns" 
        description="Portfolio growth over time compared between arms" 
      />

      <Card title="Growth Trajectory" className="flex-grow">
        <div style={{ height: CHART_DIMENSIONS.height }}>
          <MultiLineChart 
            data={data} 
            xKey="date" 
            lines={lines} 
            tickFormatter={(val: number) => formatPercent(val, 1)}
            tooltipFormatter={(val: number) => formatPercent(val)} 
          />
        </div>
        <ArmLegend arms={lines} showInaccurate={true} />
      </Card>
    </div>
  );
};

export default CumulativeReturns;
