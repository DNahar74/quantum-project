import React, { Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { LoadingState } from '../components/ui/LoadingState';

const ComparisonOverview = React.lazy(() => import('../pages/ComparisonOverview'));
const CumulativeReturns = React.lazy(() => import('../pages/CumulativeReturns'));
const AllocationOverTime = React.lazy(() => import('../pages/AllocationOverTime'));
const Drawdown = React.lazy(() => import('../pages/Drawdown'));
const RunHistory = React.lazy(() => import('../pages/RunHistory'));

export const AppRoutes: React.FC = () => {
  return (
    <AppShell>
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route path="/" element={<ComparisonOverview />} />
          <Route path="/cumulative" element={<CumulativeReturns />} />
          <Route path="/allocation" element={<AllocationOverTime />} />
          <Route path="/drawdown" element={<Drawdown />} />
          <Route path="/history" element={<RunHistory />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
};
