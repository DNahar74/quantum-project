// Turns an on-screen chart into a self-contained figure file (title, chart, legend) for papers.

const SVG_NS = 'http://www.w3.org/2000/svg';
const FONT = 'Inter, Helvetica, Arial, sans-serif';

export interface FigureMeta {
  title: string;
  subtitle?: string;
  legend?: { label: string; color: string }[];
}

const el = (name: string, attrs: Record<string, string | number>, text?: string): SVGElement => {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  return node;
};

const findChartSvg = (container: HTMLElement): SVGSVGElement | null =>
  container.querySelector('svg.recharts-surface') ?? container.querySelector('svg');

const buildFigure = (container: HTMLElement, meta: FigureMeta): { svg: string; width: number; height: number } | null => {
  const chart = findChartSvg(container);
  if (!chart) return null;
  const { width, height } = chart.getBoundingClientRect();

  const pad = 16;
  const titleH = meta.subtitle ? 52 : 34;
  const legend = meta.legend ?? [];
  const itemW = 120;
  const perRow = Math.max(1, Math.floor((width - 2 * pad) / itemW));
  const legendH = legend.length ? Math.ceil(legend.length / perRow) * 20 + 12 : 0;
  const W = Math.round(width);
  const H = Math.round(titleH + height + legendH + pad);

  const out = el('svg', { xmlns: SVG_NS, width: W, height: H, viewBox: `0 0 ${W} ${H}` }) as SVGSVGElement;
  out.appendChild(el('rect', { x: 0, y: 0, width: W, height: H, fill: '#ffffff' }));
  out.appendChild(el('text', { x: pad, y: 24, 'font-family': FONT, 'font-size': 15, 'font-weight': 600, fill: '#0f172a' }, meta.title));
  if (meta.subtitle) {
    out.appendChild(el('text', { x: pad, y: 42, 'font-family': FONT, 'font-size': 11.5, fill: '#475569' }, meta.subtitle));
  }

  const body = el('g', { transform: `translate(0, ${titleH})` });
  const clone = chart.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('width', String(width));
  clone.setAttribute('height', String(height));
  body.appendChild(clone);
  out.appendChild(body);

  legend.forEach((item, i) => {
    const x = pad + (i % perRow) * itemW;
    const y = titleH + height + 8 + Math.floor(i / perRow) * 20;
    out.appendChild(el('rect', { x, y, width: 11, height: 11, fill: item.color }));
    out.appendChild(el('text', { x: x + 16, y: y + 10, 'font-family': FONT, 'font-size': 12, fill: '#334155' }, item.label));
  });

  return { svg: new XMLSerializer().serializeToString(out), width: W, height: H };
};

const download = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export const exportSvg = (container: HTMLElement, meta: FigureMeta, filename: string) => {
  const fig = buildFigure(container, meta);
  if (fig) download(new Blob([fig.svg], { type: 'image/svg+xml' }), `${filename}.svg`);
};

/** PNG at 3x screen resolution (about 300 dpi at typical column widths). */
export const exportPng = (container: HTMLElement, meta: FigureMeta, filename: string, scale = 3) => {
  const fig = buildFigure(container, meta);
  if (!fig) return;
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = fig.width * scale;
    canvas.height = fig.height * scale;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    canvas.toBlob(blob => blob && download(blob, `${filename}.png`), 'image/png');
  };
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(fig.svg)}`;
};

export const exportCsv = (header: string[], rows: (string | number)[][], filename: string) => {
  const escape = (v: string | number) => (typeof v === 'string' && /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : String(v));
  const text = [header, ...rows].map(r => r.map(escape).join(',')).join('\n');
  download(new Blob([text], { type: 'text/csv' }), `${filename}.csv`);
};
