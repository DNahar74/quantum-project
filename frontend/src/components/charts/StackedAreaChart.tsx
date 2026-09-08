import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_THEME } from '../../lib/theme/chartTheme';
import { ASSET_COLORS } from '../../lib/theme/armColors';

interface StackedAreaChartProps {
  data: any[];
  xKey: string;
  areas: string[];
  tickFormatter?: (val: number) => string;
  tooltipFormatter?: (val: number) => string | [string, string];
}

export const StackedAreaChart: React.FC<StackedAreaChartProps> = ({ 
  data, xKey, areas, tickFormatter, tooltipFormatter 
}) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={CHART_THEME.margin}>
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
        />
        {areas.map((area, i) => (
          <Area 
            key={area} 
            type="monotone" 
            dataKey={area} 
            stackId="1" 
            stroke={ASSET_COLORS[i % ASSET_COLORS.length]} 
            fill={ASSET_COLORS[i % ASSET_COLORS.length]} 
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
};
