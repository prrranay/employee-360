import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { CeoDashboardView } from '../../components/dashboard/CeoDashboardView';
import { ManagerDashboardView } from '../../components/dashboard/ManagerDashboardView';
import { EmployeeDashboardView } from '../../components/dashboard/EmployeeDashboardView';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';

export const DashboardPage: React.FC = () => {
  const { isCeo, isManager, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSkeleton rows={6} height="h-20" />;
  }

  if (isCeo) {
    return <CeoDashboardView />;
  }

  if (isManager) {
    return <ManagerDashboardView />;
  }

  return <EmployeeDashboardView />;
};

