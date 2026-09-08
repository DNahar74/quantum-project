import React from 'react';
import { getArmColor } from '../../lib/theme/armColors';

interface ArmLegendProps {
  arms: string[];
  showInaccurate?: boolean;
}

export const ArmLegend: React.FC<ArmLegendProps> = ({ arms, showInaccurate = false }) => {
  return (
    <div className="flex flex-wrap gap-4 mt-4 text-sm text-slate-600 justify-center">
      {arms.map(arm => (
        <div key={arm} className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: getArmColor(arm) }}></span>
          <span className="capitalize">{arm}</span>
        </div>
      ))}
      {showInaccurate && (
        <div className="flex items-center gap-2 ml-4">
          <span className="w-3 h-3 rounded-full border-2 border-red-500 bg-white"></span>
          <span>Non-optimal solve</span>
        </div>
      )}
    </div>
  );
};
