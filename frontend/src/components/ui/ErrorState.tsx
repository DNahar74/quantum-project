import React from 'react';

export const ErrorState: React.FC<{ error: Error }> = ({ error }) => (
  <div className="p-6 bg-red-50 border border-red-100 rounded-xl text-red-700">
    <h3 className="font-semibold mb-1">Failed to load data</h3>
    <p className="text-sm opacity-90">{error.message}</p>
  </div>
);
