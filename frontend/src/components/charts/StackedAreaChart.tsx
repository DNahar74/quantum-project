import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { CHART_THEME } from '../../lib/theme/chartTheme';

interface StackedAreaChartProps {
  data: any[];
  xKey: string;
  areas: string[];                 // stacking order, bottom first
  colors: Record<string, string>;
  yLabel?: string;
  tickFormatter?: (val: number) => string;
  tooltipFormatter?: (val: number) => string;
}

// Lists only the holdings present at that point, largest first.
const HoldingsTooltip: React.FC<any> = ({ active, payload, label, formatter }) => {
  if (!active || !payload?.length) return null;
  const held = payload
    .filter((p: any) => p.value > 0.0005)
    .sort((a: any, b: any) => b.value - a.value);
  return (
    <div style={{ ...CHART_THEME.tooltip, padding: '8px 12px' }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {held.map((p: any) => (
        <div key={p.dataKey} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: p.color, display: 'inline-block' }} />
          <span style={{ flex: 1 }}>{p.dataKey}</span>
          <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatter ? formatter(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  );
};

/** 100% stacked weights; stepAfter because weights are held constant between rebalances. */
export const StackedAreaChart: React.FC<StackedAreaChartProps> = ({
  data, xKey, areas, colors, yLabel, tickFormatter, tooltipFormatter
}) => {
  const tick = { fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor };
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ ...CHART_THEME.margin, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={CHART_THEME.gridColor} />
        <XAxis dataKey={xKey} tick={tick} axisLine={{ stroke: CHART_THEME.axisColor }} tickLine={false} minTickGap={40} dy={10} />
        <YAxis
          domain={[0, 1]}
          ticks={[0, 0.25, 0.5, 0.75, 1]}
          allowDataOverflow
          tickFormatter={tickFormatter}
          tick={tick}
          axisLine={false}
          tickLine={false}
          label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', offset: -10, style: { ...tick, textAnchor: 'middle' } } : undefined}
        />
        <Tooltip content={<HoldingsTooltip formatter={tooltipFormatter} />} />
        {areas.map(area => (
          <Area
            key={area}
            type="stepAfter"
            dataKey={area}
            stackId="1"
            stroke="none"
            fill={colors[area]}
            fillOpacity={1}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
};
