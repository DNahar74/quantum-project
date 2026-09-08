import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_THEME } from '../../lib/theme/chartTheme';

interface GroupedBarChartProps {
  data: any[];
  xKey: string;
  yKey: string;
  color: string;
  tickFormatter?: (val: number) => string;
  tooltipFormatter?: (val: number) => string | [string, string];
}

export const GroupedBarChart: React.FC<GroupedBarChartProps> = ({ 
  data, xKey, yKey, color, tickFormatter, tooltipFormatter 
}) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={CHART_THEME.margin}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={CHART_THEME.gridColor} />
        <XAxis 
          dataKey={xKey} 
          tick={{ fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor }}
          axisLine={{ stroke: CHART_THEME.axisColor }}
          tickLine={false}
          dy={10}
        />
        <YAxis 
          tickFormatter={tickFormatter}
          tick={{ fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor }}
          axisLine={false}
          tickLine={false}
          dx={-10}
        />
        <Tooltip 
          formatter={tooltipFormatter as any}
          contentStyle={CHART_THEME.tooltip}
          cursor={{ fill: '#f1f5f9' }}
        />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
};
