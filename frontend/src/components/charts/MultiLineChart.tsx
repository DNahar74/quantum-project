import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_THEME } from '../../lib/theme/chartTheme';
import { SolverStatusMarker } from './SolverStatusMarker';
import { getArmColor } from '../../lib/theme/armColors';

interface MultiLineChartProps {
  data: any[];
  xKey: string;
  lines: string[];
  tickFormatter?: (val: number) => string;
  tooltipFormatter?: (val: number) => string | [string, string];
}

export const MultiLineChart: React.FC<MultiLineChartProps> = ({ 
  data, xKey, lines, tickFormatter, tooltipFormatter 
}) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={CHART_THEME.margin}>
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
        {lines.map((line) => (
          <Line 
            key={line}
            type="monotone" 
            dataKey={line} 
            stroke={getArmColor(line)} 
            strokeWidth={2} 
            dot={<SolverStatusMarker />} 
            activeDot={{ r: 6, strokeWidth: 0 }} 
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
};
