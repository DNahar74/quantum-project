import React, { useEffect, useMemo, useRef, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAllocationRows, ARMS, type Arm } from './AllocationOverTime.hooks';
import { PageHeader } from '../../components/ui/PageHeader';
import { LoadingState } from '../../components/ui/LoadingState';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { StackedAreaChart } from '../../components/charts/StackedAreaChart';
import { WeightHeatmap } from '../../components/charts/WeightHeatmap';
import { formatNumber, formatPercent } from '../../lib/utils/format';
import { CHART_THEME } from '../../lib/theme/chartTheme';
import { assetColorMap, getArmColor } from '../../lib/theme/armColors';
import { aggregate, autoBucket, summarize, BUCKET_LABEL, type Bucket, type Period } from '../../lib/utils/allocation';
import { exportCsv, exportPng, exportSvg, type FigureMeta } from '../../lib/utils/exportFigure';

const ARM_LABEL: Record<Arm, string> = { markowitz: 'Markowitz', qaoa: 'QAOA' };
const PRESETS = [
  { key: '1Y', years: 1 }, { key: '3Y', years: 3 }, { key: '5Y', years: 5 },
  { key: '10Y', years: 10 }, { key: '25Y', years: 25 }, { key: 'All', years: null },
] as const;

const yearsBefore = (date: string, years: number): string => {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCFullYear(d.getUTCFullYear() - years);
  return d.toISOString().slice(0, 10);
};

const Segmented: React.FC<{ options: { key: string; label: string }[]; value: string; onChange: (v: string) => void }> = ({ options, value, onChange }) => (
  <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm">
    {options.map(o => (
      <button key={o.key} onClick={() => onChange(o.key)}
        className={`px-3 py-1.5 text-sm font-medium rounded-md ${value === o.key ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
        {o.label}
      </button>
    ))}
  </div>
);

interface FigureProps {
  number: number;
  meta: FigureMeta;
  caption: string;
  filename: string;
  csv: { header: string[]; rows: (string | number)[][] };
  height?: number;
  children: React.ReactNode;
}

/** A numbered figure with a citable caption and SVG / PNG / CSV export. */
const Figure: React.FC<FigureProps> = ({ number, meta, caption, filename, csv, height, children }) => {
  const ref = useRef<HTMLDivElement>(null);
  const btn = 'px-2.5 py-1 text-xs font-medium rounded-md border border-slate-200 text-slate-600 hover:bg-slate-100';
  return (
    <figure className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 m-0">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-800">{meta.title}</h3>
          {meta.subtitle && <p className="text-sm text-slate-500 mt-1">{meta.subtitle}</p>}
        </div>
        <div className="flex gap-1.5">
          <button className={btn} onClick={() => ref.current && exportSvg(ref.current, meta, filename)}>SVG</button>
          <button className={btn} onClick={() => ref.current && exportPng(ref.current, meta, filename)}>PNG</button>
          <button className={btn} onClick={() => exportCsv(csv.header, csv.rows, filename)}>CSV</button>
        </div>
      </div>
      <div ref={ref} style={height ? { height } : undefined}>{children}</div>
      {meta.legend && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-4">
          {meta.legend.map(l => (
            <span key={l.label} className="inline-flex items-center gap-1.5 text-xs text-slate-600">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ background: l.color }} />{l.label}
            </span>
          ))}
        </div>
      )}
      <figcaption className="text-sm text-slate-600 mt-4 pt-3 border-t border-slate-100">
        <span className="font-semibold">Figure {number}.</span> {caption}
      </figcaption>
    </figure>
  );
};

const AllocationOverTime: React.FC = () => {
  const { rows, assets, minDate, maxDate, status, error } = useAllocationRows();
  const [armChoice, setArmChoice] = useState<'markowitz' | 'qaoa' | 'both'>('markowitz');
  const [preset, setPreset] = useState<string>('All');
  const [from, setFrom] = useState<string>('');
  const [to, setTo] = useState<string>('');
  const [bucketChoice, setBucketChoice] = useState<'auto' | Bucket>('auto');

  // Presets always end at the last rebalance; editing a date switches to a custom window.
  useEffect(() => {
    if (!minDate || !maxDate) return;
    const p = PRESETS.find(x => x.key === preset);
    if (!p) return;
    setTo(maxDate);
    setFrom(p.years === null ? minDate : [yearsBefore(maxDate, p.years), minDate].sort()[1]);
  }, [preset, minDate, maxDate]);

  const arms: Arm[] = armChoice === 'both' ? [...ARMS] : [armChoice];
  const colors = useMemo(() => assetColorMap(assets), [assets]);
  const bucket: Bucket = bucketChoice === 'auto' && from && to ? autoBucket(from, to) : (bucketChoice === 'auto' ? 'month' : bucketChoice);

  const view = useMemo(() => Object.fromEntries(arms.map(arm => {
    const windowRows = rows[arm].filter(r => r.rebalance_date >= from && r.rebalance_date <= to);
    return [arm, { rows: windowRows, periods: aggregate(windowRows, assets, bucket), summary: summarize(windowRows, assets) }];
  })) as Record<Arm, { rows: typeof rows.markowitz; periods: Period[]; summary: ReturnType<typeof summarize> }>,
  [rows, arms.join(), from, to, assets, bucket]);

  if (status === 'loading' || status === 'idle') return <LoadingState />;
  if (status === 'error' && error) return <ErrorState error={error} />;
  if (!minDate || !maxDate) return <EmptyState message="No backtest results yet" />;

  const legend = assets.map(a => ({ label: a, color: colors[a] }));
  const anyRow = rows.markowitz[0] ?? rows.qaoa[0];
  const q = anyRow?.risk_aversion;
  const windowText = `${from} to ${to}`;
  const settingsText = `Long-only, per-asset caps, weekly rebalancing${q !== undefined ? `, risk aversion q = ${q}` : ''}.`;
  const aggText = bucket === 'week' ? 'weights at each weekly rebalance' : `${BUCKET_LABEL[bucket]} averages of weekly rebalance weights`;
  const maxWeight = Math.max(0.05, ...arms.flatMap(a => view[a].periods.flatMap(p => Object.values(p.weights))));
  const heatMax = Math.ceil(maxWeight * 20) / 20;  // round up to 5%

  let fig = 0;
  const effNData = (() => {
    const byLabel = new Map<string, Record<string, number | string>>();
    for (const arm of arms) for (const p of view[arm].periods) {
      const point = byLabel.get(p.label) ?? { date: p.label };
      point[arm] = p.effectiveN;
      byLabel.set(p.label, point);
    }
    return [...byLabel.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  })();

  const select = 'px-3 py-1.5 border border-slate-200 rounded-lg shadow-sm bg-white text-sm text-slate-700';

  return (
    <div className="space-y-6">
      <PageHeader title="Allocation Over Time" description="Portfolio weights per industry across rebalance dates" />

      <div className="flex flex-wrap items-end gap-4 bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">Optimizer
          <Segmented value={armChoice} onChange={v => setArmChoice(v as typeof armChoice)}
            options={[{ key: 'markowitz', label: 'Markowitz' }, { key: 'qaoa', label: 'QAOA' }, { key: 'both', label: 'Both' }]} />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">Window
          <Segmented value={preset} onChange={setPreset} options={PRESETS.map(p => ({ key: p.key, label: p.key }))} />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">From
          <input type="date" className={select} value={from} min={minDate} max={to || maxDate}
            onChange={e => { setPreset('Custom'); setFrom(e.target.value); }} />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">To
          <input type="date" className={select} value={to} min={from || minDate} max={maxDate}
            onChange={e => { setPreset('Custom'); setTo(e.target.value); }} />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">Aggregation
          <select className={select} value={bucketChoice} onChange={e => setBucketChoice(e.target.value as typeof bucketChoice)}>
            <option value="auto">Auto ({BUCKET_LABEL[from && to ? autoBucket(from, to) : 'month']})</option>
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
            <option value="quarter">Quarterly</option>
            <option value="year">Yearly</option>
          </select>
        </label>
      </div>

      {arms.map(arm => {
        const v = view[arm];
        if (v.rows.length === 0) return <EmptyState key={arm} message={`No ${ARM_LABEL[arm]} rebalances in this window`} />;
        const data = v.periods.map(p => ({ date: p.label, ...p.weights }));
        return (
          <Figure key={`area-${arm}`} number={++fig} height={420}
            filename={`weights_${arm}_${from}_${to}_${bucket}`}
            meta={{ title: `${ARM_LABEL[arm]} portfolio weights`, subtitle: `${windowText} · ${v.rows.length} weekly rebalances · ${aggText}`, legend }}
            caption={`Portfolio weights of the ${ARM_LABEL[arm]} optimizer, ${windowText}, shown as ${aggText}. Each band is one industry; bands sum to 100%. ${settingsText}`}
            csv={{ header: ['period', 'start', 'end', 'rebalances', ...assets],
                   rows: v.periods.map(p => [p.label, p.start, p.end, p.nRebalances, ...assets.map(a => +p.weights[a].toFixed(6))]) }}>
            <StackedAreaChart data={data} xKey="date" areas={assets} colors={colors} yLabel="Portfolio weight"
              tickFormatter={(val: number) => formatPercent(val, 0)} tooltipFormatter={(val: number) => formatPercent(val, 1)} />
          </Figure>
        );
      })}

      {arms.map(arm => view[arm].rows.length > 0 && (
        <Figure key={`heat-${arm}`} number={++fig}
          filename={`weight_heatmap_${arm}_${from}_${to}_${bucket}`}
          meta={{ title: `${ARM_LABEL[arm]} weight heatmap`, subtitle: `${windowText} · ${aggText}` }}
          caption={`Average portfolio weight of each industry (rows) per ${bucket === 'week' ? 'rebalance' : bucket} (columns) for the ${ARM_LABEL[arm]} optimizer, ${windowText}. Darker cells are larger weights; white means not held. Color scale 0–${formatPercent(heatMax, 0)}, shared across optimizers. ${settingsText}`}
          csv={{ header: ['period', ...assets], rows: view[arm].periods.map(p => [p.label, ...assets.map(a => +p.weights[a].toFixed(6))]) }}>
          <WeightHeatmap periods={view[arm].periods} assets={assets} maxWeight={heatMax} />
        </Figure>
      ))}

      <Figure number={++fig} height={320}
        filename={`effective_holdings_${armChoice}_${from}_${to}_${bucket}`}
        meta={{ title: 'Portfolio concentration', subtitle: `${windowText} · effective number of holdings, 1 / Σw²`,
                legend: arms.map(a => ({ label: ARM_LABEL[a], color: getArmColor(a) })) }}
        caption={`Effective number of holdings, 1/Σᵢwᵢ² (the inverse Herfindahl index of the weights), ${windowText}, ${bucket === 'week' ? 'at each rebalance' : `averaged per ${bucket}`}. A value of N means the portfolio is as diversified as N equal weights; the maximum is ${assets.length}. ${settingsText}`}
        csv={{ header: ['period', ...arms.map(a => `${a}_effective_n`)], rows: effNData.map(p => [String(p.date), ...arms.map(a => +Number(p[a] ?? NaN).toFixed(4))]) }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={effNData} margin={{ ...CHART_THEME.margin, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={CHART_THEME.gridColor} />
            <XAxis dataKey="date" minTickGap={40} tickLine={false} dy={10}
              tick={{ fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor }} axisLine={{ stroke: CHART_THEME.axisColor }} />
            <YAxis domain={[1, assets.length]} allowDecimals={false} axisLine={false} tickLine={false}
              tick={{ fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor }}
              label={{ value: 'Effective no. of holdings', angle: -90, position: 'insideLeft', offset: -10,
                       style: { fontFamily: CHART_THEME.fontFamily, fontSize: CHART_THEME.fontSize, fill: CHART_THEME.axisColor, textAnchor: 'middle' } }} />
            <Tooltip formatter={((val: number) => formatNumber(val, 2)) as any} contentStyle={CHART_THEME.tooltip} />
            {arms.map(a => <Line key={a} type="stepAfter" dataKey={a} name={ARM_LABEL[a]} stroke={getArmColor(a)} strokeWidth={1.75} dot={false} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </Figure>

      <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-800">Table 1. Allocation summary</h3>
            <p className="text-sm text-slate-500 mt-1">{windowText} · statistics over every weekly rebalance in the window</p>
          </div>
          <button className="px-2.5 py-1 text-xs font-medium rounded-md border border-slate-200 text-slate-600 hover:bg-slate-100"
            onClick={() => exportCsv(
              ['industry', ...arms.flatMap(a => [`${a}_mean_weight`, `${a}_max_weight`, `${a}_share_held`])],
              assets.map(asset => [asset, ...arms.flatMap(a => {
                const s = view[a].summary.assets.find(x => x.asset === asset)!;
                return [+s.mean.toFixed(6), +s.max.toFixed(6), +s.heldShare.toFixed(6)];
              })]),
              `allocation_summary_${armChoice}_${from}_${to}`)}>CSV</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="border-b border-slate-300 text-slate-500">
                <th className="text-left font-medium py-2 pr-4" rowSpan={2}>Industry</th>
                {arms.map(a => <th key={a} colSpan={3} className="font-semibold text-slate-700 py-1 px-2 text-center">{ARM_LABEL[a]}</th>)}
              </tr>
              <tr className="border-b border-slate-300 text-slate-500">
                {arms.flatMap(a => [
                  <th key={`${a}m`} className="text-right font-medium py-1 px-2">Mean weight</th>,
                  <th key={`${a}x`} className="text-right font-medium py-1 px-2">Max weight</th>,
                  <th key={`${a}h`} className="text-right font-medium py-1 px-2">% weeks held</th>,
                ])}
              </tr>
            </thead>
            <tbody>
              {assets.map(asset => (
                <tr key={asset} className="border-b border-slate-100">
                  <td className="py-1.5 pr-4"><span className="inline-block w-2.5 h-2.5 rounded-sm mr-2 align-middle" style={{ background: colors[asset] }} />{asset}</td>
                  {arms.flatMap(a => {
                    const s = view[a].summary.assets.find(x => x.asset === asset)!;
                    return [
                      <td key={`${a}m`} className="text-right py-1.5 px-2">{formatPercent(s.mean, 1)}</td>,
                      <td key={`${a}x`} className="text-right py-1.5 px-2">{formatPercent(s.max, 1)}</td>,
                      <td key={`${a}h`} className="text-right py-1.5 px-2">{formatPercent(s.heldShare, 0)}</td>,
                    ];
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot className="text-slate-700">
              {[
                { label: 'Weekly rebalances', f: (a: Arm) => String(view[a].summary.nRebalances) },
                { label: 'Avg. number of holdings', f: (a: Arm) => formatNumber(view[a].summary.avgHoldings, 2) },
                { label: 'Avg. effective holdings (1/Σw²)', f: (a: Arm) => formatNumber(view[a].summary.avgEffectiveN, 2) },
                { label: 'Avg. weekly turnover (Σ|Δw|)', f: (a: Arm) => formatPercent(view[a].summary.avgTurnover, 1) },
              ].map(r => (
                <tr key={r.label} className="border-t border-slate-200">
                  <td className="py-1.5 pr-4 font-medium">{r.label}</td>
                  {arms.map(a => <td key={a} colSpan={3} className="text-right py-1.5 px-2">{r.f(a)}</td>)}
                </tr>
              ))}
            </tfoot>
          </table>
        </div>
        <p className="text-sm text-slate-600 mt-4 pt-3 border-t border-slate-100">
          <span className="font-semibold">Table 1.</span> Weight statistics per industry over the weekly rebalances from {windowText}. “% weeks held” counts weights above 0.1%. Turnover is Σ|w<sub>t</sub> − w<sub>t−1</sub>|; the first rebalance counts as 100%. {settingsText}
        </p>
      </section>
    </div>
  );
};

export default AllocationOverTime;
