import React from 'react';
import type { Period } from '../../lib/utils/allocation';
import { formatPercent } from '../../lib/utils/format';

interface WeightHeatmapProps {
  periods: Period[];
  assets: string[];
  maxWeight: number;  // top of the color scale
}

const FONT = 'Inter, Helvetica, Arial, sans-serif';

// Sequential single-hue scale (ColorBrewer Blues), readable in greyscale print.
const BLUES = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'];

const hexToRgb = (h: string) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

export const blues = (t: number): string => {
  const x = Math.min(1, Math.max(0, t)) * (BLUES.length - 1);
  const i = Math.min(BLUES.length - 2, Math.floor(x));
  const f = x - i;
  const [a, b] = [hexToRgb(BLUES[i]), hexToRgb(BLUES[i + 1])];
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(',')})`;
};

/** Assets (rows) x periods (columns), cell color = average weight. Native tooltips on hover. */
export const WeightHeatmap: React.FC<WeightHeatmapProps> = ({ periods, assets, maxWeight }) => {
  const W = 1000;
  const left = 64, right = 16, top = 8, rowH = 22;
  const plotW = W - left - right;
  const plotH = assets.length * rowH;
  const axisY = top + plotH;
  const barY = axisY + 40;
  const H = barY + 34;
  const cellW = plotW / Math.max(1, periods.length);

  const nTicks = Math.min(periods.length, 8);
  const tickIdx = Array.from({ length: nTicks }, (_, i) => Math.round((i * (periods.length - 1)) / Math.max(1, nTicks - 1)));
  const barW = 260, barX = W - right - barW;
  const scaleTicks = [0, 0.25, 0.5, 0.75, 1].map(f => f * maxWeight);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }} xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="weight-scale" x1="0" x2="1" y1="0" y2="0">
          {BLUES.map((c, i) => <stop key={c} offset={i / (BLUES.length - 1)} stopColor={c} />)}
        </linearGradient>
      </defs>

      {assets.map((asset, r) => (
        <g key={asset}>
          <text x={left - 8} y={top + r * rowH + rowH / 2 + 4} textAnchor="end" fontFamily={FONT} fontSize={12} fill="#334155">{asset}</text>
          {periods.map((p, c) => (
            <rect key={p.label} x={left + c * cellW} y={top + r * rowH} width={cellW + 0.5} height={rowH - 1}
                  fill={blues(p.weights[asset] / maxWeight)}>
              <title>{`${asset}, ${p.label}: ${formatPercent(p.weights[asset], 1)}`}</title>
            </rect>
          ))}
        </g>
      ))}

      <line x1={left} x2={W - right} y1={axisY} y2={axisY} stroke="#64748b" />
      {tickIdx.map(i => (
        <text key={i} x={left + (i + 0.5) * cellW} y={axisY + 16} textAnchor="middle" fontFamily={FONT} fontSize={11} fill="#64748b">
          {periods[i]?.label}
        </text>
      ))}

      <text x={barX - 10} y={barY + 10} textAnchor="end" fontFamily={FONT} fontSize={11} fill="#334155">Average weight</text>
      <rect x={barX} y={barY} width={barW} height={12} fill="url(#weight-scale)" stroke="#cbd5e1" />
      {scaleTicks.map(v => (
        <text key={v} x={barX + (v / maxWeight) * barW} y={barY + 26} textAnchor="middle" fontFamily={FONT} fontSize={10.5} fill="#64748b">
          {formatPercent(v, 0)}
        </text>
      ))}
    </svg>
  );
};
