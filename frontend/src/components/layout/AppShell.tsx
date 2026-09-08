import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, BarChart2, PieChart, TrendingDown, Clock } from 'lucide-react';
import { useRuns } from '../../lib/hooks/useRuns';

const NavLink = ({ to, icon: Icon, children }: { to: string; icon: any; children: React.ReactNode }) => {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`flex items-center space-x-3 px-4 py-2.5 rounded-lg transition-colors font-medium ${
        isActive ? 'bg-slate-800 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
      }`}
    >
      <Icon size={18} />
      <span>{children}</span>
    </Link>
  );
};

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data } = useRuns();

  return (
    <div className="flex h-screen bg-slate-50">
      <div className="w-64 bg-white shadow-sm border-r border-slate-200 flex flex-col z-10">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-xl font-bold text-slate-900">Quantum QAOA</h1>
          <p className="text-sm text-slate-500 mt-1">Backtest Analysis</p>
        </div>
        
        <nav className="p-4 flex flex-col space-y-1 flex-grow">
          <NavLink to="/" icon={BarChart2}>Comparison Overview</NavLink>
          <NavLink to="/cumulative" icon={Activity}>Cumulative Returns</NavLink>
          <NavLink to="/allocation" icon={PieChart}>Allocation</NavLink>
          <NavLink to="/drawdown" icon={TrendingDown}>Drawdown</NavLink>
          <NavLink to="/history" icon={Clock}>Run History</NavLink>
        </nav>
        
        <div className="p-6 border-t border-slate-200 text-sm text-slate-500">
          {data?.start_date && data?.end_date ? (
            <div>Active Range:<br/><span className="font-medium text-slate-700">{data.start_date}</span> to <span className="font-medium text-slate-700">{data.end_date}</span></div>
          ) : (
            <div>No active runs.</div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <main className="p-8 max-w-7xl mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
