import React from 'react';
import { useDrawdownData } from './Drawdown.hooks';
import { useRuns } from '../../lib/hooks/useRuns';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { ShadedDrawdownChart } from '../../components/charts/ShadedDrawdownChart';
import { ArmLegend } from '../../components/ui/ArmLegend';
import { formatPercent } from '../../lib/utils/format';
import { CHART_DIMENSIONS } from '../../lib/theme/chartTheme';

const Drawdown: React.FC = () => {
  const { data: runData } = useRuns();
  const { data, status, error } = useDrawdownData(runData?.start_date, runData?.end_date);

  if (status === 'loading') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (!runData?.start_date || (status === 'success' && data.length === 0)) {
    return <EmptyState message="No runs in this date range" />;
  }

  const areas = ['markowitz', 'qaoa'];

  return (
    <div className="space-y-6 flex flex-col h-full">
      <PageHeader 
        title="Drawdown" 
        description="Peak-to-trough decline over time" 
      />

      <Card title="Relative Drawdown" className="flex-grow">
        <div style={{ height: CHART_DIMENSIONS.height }}>
          <ShadedDrawdownChart 
            data={data} 
            xKey="date" 
            areas={areas} 
            tickFormatter={(val: number) => formatPercent(val, 1)}
            tooltipFormatter={(val: number) => formatPercent(val)} 
          />
        </div>
        <ArmLegend arms={areas} />
      </Card>
    </div>
  );
};

export default Drawdown;
