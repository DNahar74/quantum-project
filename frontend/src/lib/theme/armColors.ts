const ARM_COLORS: Record<string, string> = {
  markowitz: '#2563eb', // Blue
  qaoa: '#7c3aed',      // Purple
  sp500: '#10b981'      // Green (if benchmark used)
};

export const getArmColor = (arm: string): string => {
  const normalized = arm.toLowerCase();
  return ARM_COLORS[normalized] || '#64748b';
};

// Tableau 10 plus two, all distinct on white. Colors are assigned by an asset's position in the
// returns file (see assetColorMap), so an industry keeps its color across windows, arms and figures.
export const ASSET_COLORS = [
  '#4e79a7', // blue
  '#f28e2b', // orange
  '#e15759', // red
  '#76b7b2', // teal
  '#59a14f', // green
  '#edc948', // yellow
  '#b07aa1', // purple
  '#ff9da7', // pink
  '#9c755f', // brown
  '#79706e', // grey
  '#1f3a5f', // navy
  '#8cd17d'  // light green
];

export const assetColorMap = (assets: string[]): Record<string, string> =>
  Object.fromEntries(assets.map((a, i) => [a, ASSET_COLORS[i % ASSET_COLORS.length]]));
