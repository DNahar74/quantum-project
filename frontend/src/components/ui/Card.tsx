import React from 'react';

interface CardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ title, description, children, className = '' }) => {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col ${className}`}>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
        {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
      </div>
      <div className="flex-grow min-h-0">
        {children}
      </div>
    </div>
  );
};
