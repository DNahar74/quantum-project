import React from 'react';

interface EmptyStateProps {
  message: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ message }) => (
  <div className="flex items-center justify-center p-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50 text-slate-500">
    {message}
  </div>
);


