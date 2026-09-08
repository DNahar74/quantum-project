import React from 'react';
import { useComparisonData } from './ComparisonOverview.hooks';
import { useRuns } from '../../lib/hooks/useRuns';
import { PageHeader } from '../../components/ui/PageHeader';
import { Card } from '../../components/ui/Card';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { GroupedBarChart } from '../../components/charts/GroupedBarChart';
import { formatNumber, formatPercent } from '../../lib/utils/format';
import { CHART_DIMENSIONS } from '../../lib/theme/chartTheme';

const ComparisonOverview: React.FC = () => {
  const { data: runData } = useRuns();
  const { data, status, error } = useComparisonData(runData?.start_date, runData?.end_date);

  if (status === 'loading') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (!runData?.start_date || (status === 'success' && data.length === 0)) {
    return <EmptyState message="No runs in this date range" />;
  }

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Comparison Overview" 
        description="Comparing Markowitz vs QAOA metrics over the selected period" 
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Annualized Sharpe Ratio" description="Risk-adjusted return (higher is better)">
          <div style={{ height: CHART_DIMENSIONS.overviewHeight }}>
            <GroupedBarChart 
              data={data} 
              xKey="name" 
              yKey="Sharpe" 
              color="#3b82f6" 
              tooltipFormatter={(val: number) => formatNumber(val)} 
            />
          </div>
        </Card>

        <Card title="Max Drawdown" description="Peak-to-trough decline (lower is better)">
          <div style={{ height: CHART_DIMENSIONS.overviewHeight }}>
            <GroupedBarChart 
              data={data} 
              xKey="name" 
              yKey="MaxDrawdown" 
              color="#ef4444" 
              tickFormatter={(val: number) => formatPercent(val, 1)}
              tooltipFormatter={(val: number) => formatPercent(val)} 
            />
          </div>
        </Card>

        <Card title="Average Weekly Turnover" description="Portfolio churn per rebalance (lower is better)">
          <div style={{ height: CHART_DIMENSIONS.overviewHeight }}>
            <GroupedBarChart 
              data={data} 
              xKey="name" 
              yKey="AvgTurnover" 
              color="#10b981" 
              tickFormatter={(val: number) => formatPercent(val, 1)}
              tooltipFormatter={(val: number) => formatPercent(val)} 
            />
          </div>
        </Card>
      </div>
    </div>
  );
};

export default ComparisonOverview;
