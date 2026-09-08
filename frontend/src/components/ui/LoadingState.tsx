import React from 'react';

export const LoadingState: React.FC = () => (
  <div className="flex items-center justify-center p-12 text-slate-400">
    <div className="animate-pulse flex items-center space-x-2">
      <div className="w-2 h-2 bg-slate-400 rounded-full"></div>
      <div className="w-2 h-2 bg-slate-400 rounded-full animation-delay-200"></div>
      <div className="w-2 h-2 bg-slate-400 rounded-full animation-delay-400"></div>
      <span className="ml-2 font-medium">Loading data...</span>
    </div>
  </div>
);
