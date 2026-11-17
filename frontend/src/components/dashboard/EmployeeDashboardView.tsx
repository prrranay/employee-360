import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Clock,
  CheckCircle2,
  CalendarOff,
  Percent,
  FilePlus,
  AlertCircle
} from 'lucide-react';
import type { AttendanceTrendPoint } from '../../types';
import { employeeApi } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { PunchWidget } from '../attendance/PunchWidget';
import { KpiCard } from '../common/KpiCard';
import { AttendanceTrendChart } from '../charts/AttendanceTrendChart';
import { LeaveApplyModal } from '../leave/LeaveApplyModal';
import { CorrectionModal } from '../attendance/CorrectionModal';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

export const EmployeeDashboardView: React.FC = () => {
  const { user } = useAuth();
  const empId = user?.employee?.employee_id || 'EMP-01362';

  const [leaveModalOpen, setLeaveModalOpen] = useState(false);
  const [correctionModalOpen, setCorrectionModalOpen] = useState(false);

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['employeeSummary', empId],
    queryFn: () => employeeApi.getSummary(empId)
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ['employeeTrends', empId],
    queryFn: () => employeeApi.getTrend(empId, 14)
  });

  const trendPoints: AttendanceTrendPoint[] = (trends || []).map((t) => ({
    activity_date: t.activity_date,
    present: t.attendance_status === 'Present' ? 1 : 0,
    late: t.attendance_status === 'Late' ? 1 : 0,
    half_day: t.attendance_status === 'Half Day' ? 1 : 0,
    absent: t.attendance_status === 'Absent' ? 1 : 0,
    on_leave: t.attendance_status === 'On Leave' ? 1 : 0,
    weekly_off: t.attendance_status === 'Weekly Off' ? 1 : 0,
    missing_checkout: t.attendance_status === 'Missing Check-out' ? 1 : 0
  }));

  return (
    <div className="space-y-8">
      {/* Top Welcome Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Welcome back, {user?.employee?.employee_name || 'Team Member'}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {user?.employee?.designation} • {user?.employee?.department}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCorrectionModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
          >
            <AlertCircle className="h-4 w-4 text-amber-600" />
            Request Correction
          </button>
          <button
            onClick={() => setLeaveModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 transition"
          >
            <FilePlus className="h-4 w-4" />
            Apply Leave
          </button>
        </div>
      </div>

      {/* Live Punch Widget */}
      <PunchWidget />

      {/* 365-Day Metrics Grid */}
      <div>
        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
          Annual Attendance Overview (Past 365 Days)
        </h3>
        {loadingSummary ? (
          <LoadingSkeleton rows={1} height="h-24" />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              title="Attendance Rate"
              value={`${summary?.attendance_percentage || 0}%`}
              subtitle="Eligible workdays attended"
              icon={Percent}
              iconBg="bg-emerald-50"
              iconColor="text-emerald-600"
            />
            <KpiCard
              title="Days Present"
              value={summary?.present_count.toLocaleString() || '0'}
              subtitle="On-time sessions"
              icon={CheckCircle2}
              iconBg="bg-emerald-50"
              iconColor="text-emerald-600"
            />
            <KpiCard
              title="Late Arrivals"
              value={summary?.late_count.toLocaleString() || '0'}
              subtitle="Past grace period"
              icon={Clock}
              iconBg="bg-amber-50"
              iconColor="text-amber-600"
            />
            <KpiCard
              title="Approved Leaves"
              value={summary?.leave_count.toLocaleString() || '0'}
              subtitle="Days off taken"
              icon={CalendarOff}
              iconBg="bg-purple-50"
              iconColor="text-purple-600"
            />
          </div>
        )}
      </div>

      {/* Recent Personal Trend */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
        <h3 className="text-sm font-bold text-slate-900 mb-1">Recent 14-Day Attendance Log</h3>
        <p className="text-xs text-slate-500 mb-4">Daily work duration and attendance status</p>
        {loadingTrends ? (
          <LoadingSkeleton rows={3} height="h-20" />
        ) : (
          <AttendanceTrendChart data={trendPoints} height={260} />
        )}
      </div>

      {/* Modals */}
      <LeaveApplyModal
        isOpen={leaveModalOpen}
        onClose={() => setLeaveModalOpen(false)}
        employeeId={empId}
      />
      <CorrectionModal
        isOpen={correctionModalOpen}
        onClose={() => setCorrectionModalOpen(false)}
      />
    </div>
  );
};
