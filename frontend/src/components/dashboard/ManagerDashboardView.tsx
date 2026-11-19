import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users,
  CheckCircle,
  Clock,
  AlertTriangle,
  Percent,
  Check,
  X
} from 'lucide-react';
import { managerApi } from '../../api/client';
import { KpiCard } from '../common/KpiCard';
import { AttendanceTrendChart } from '../charts/AttendanceTrendChart';
import { LoadingSkeleton } from '../common/LoadingSkeleton';
import { ErrorState } from '../common/ErrorState';
import { formatDate } from '../../utils/formatters';

export const ManagerDashboardView: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState('2026-11-16');

  const { data: teamSummary, isLoading: loadingSummary, error: errSummary } = useQuery({
    queryKey: ['teamSummary', selectedDate],
    queryFn: () => managerApi.getTeamSummary(selectedDate, 1)
  });

  const { data: teamTrends, isLoading: loadingTrends } = useQuery({
    queryKey: ['teamTrends'],
    queryFn: () => managerApi.getTeamAttendanceTrend(undefined, selectedDate, 14, 1)
  });

  const { data: teamLeaves, isLoading: loadingLeaves } = useQuery({
    queryKey: ['teamLeaves'],
    queryFn: () => managerApi.getTeamLeaves('Pending', 1, 5)
  });

  const { data: exceptions, isLoading: loadingExceptions } = useQuery({
    queryKey: ['teamExceptions', selectedDate],
    queryFn: () => managerApi.getTeamExceptions(selectedDate, undefined, 1, 5, 1)
  });

  const approveMutation = useMutation({
    mutationFn: (leaveId: string) => managerApi.approveLeave(leaveId, 'Approved by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['teamSummary'] });
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (leaveId: string) => managerApi.rejectLeave(leaveId, 'Rejected by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamLeaves'] });
    }
  });

  if (errSummary) {
    return <ErrorState message="Could not load team summary data." />;
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header & Date */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">Team Operations Dashboard</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Attendance monitoring and approvals for direct and indirect reports
          </p>
        </div>
        <div className="flex items-center justify-between sm:justify-start gap-2 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 pl-2">Filter Date:</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-800 focus:outline-none"
          />
        </div>
      </div>

      {/* Team KPI Cards */}
      {loadingSummary ? (
        <LoadingSkeleton rows={1} height="h-24" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <KpiCard
            title="Team Headcount"
            value={teamSummary?.team_size || 0}
            subtitle="Reports"
            icon={Users}
            iconBg="bg-indigo-50"
            iconColor="text-indigo-600"
          />
          <KpiCard
            title="Team Attendance"
            value={`${teamSummary?.attendance_rate || 0}%`}
            subtitle="Attendance rate today"
            icon={Percent}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Present Today"
            value={teamSummary?.present || 0}
            subtitle="On-time team members"
            icon={CheckCircle}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Late / Anomalies"
            value={(teamSummary?.late || 0) + (teamSummary?.missing_checkout || 0)}
            subtitle="Requires team review"
            icon={Clock}
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
          />
        </div>
      )}

      {/* Main Charts & Pending Approvals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Team Attendance Trajectory */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">14-Day Team Attendance Trend</h3>
          <p className="text-xs text-slate-500 mb-4">Daily attendance status distribution</p>
          {loadingTrends ? (
            <LoadingSkeleton rows={3} height="h-20" />
          ) : (
            <AttendanceTrendChart data={teamTrends || []} height={260} />
          )}
        </div>

        {/* Pending Leave Approvals Drawer */}
        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900">Pending Leave Requests</h3>
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-bold text-indigo-700">
                {teamLeaves?.total || 0} Pending
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-4">Requires your managerial decision</p>

            {loadingLeaves ? (
              <LoadingSkeleton rows={3} height="h-14" />
            ) : !teamLeaves?.records || teamLeaves.records.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No pending leave requests from your team.
              </div>
            ) : (
              <div className="space-y-3">
                {teamLeaves.records.map((req) => (
                  <div
                    key={req.name}
                    className="rounded-xl border border-slate-200/80 p-3 text-xs bg-slate-50/50"
                  >
                    <div className="flex items-center justify-between font-semibold text-slate-900">
                      <span>{req.employee_name || req.employee}</span>
                      <span className="text-[10px] text-indigo-600">{req.leave_type}</span>
                    </div>
                    <div className="mt-1 text-[11px] text-slate-500">
                      {formatDate(req.from_date)} – {formatDate(req.to_date)}
                    </div>
                    <div className="mt-1 text-slate-600 italic text-[11px] truncate">
                      "{req.reason}"
                    </div>

                    <div className="mt-3 flex items-center justify-end gap-2">
                      <button
                        onClick={() => rejectMutation.mutate(req.name)}
                        disabled={rejectMutation.isPending}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5 text-rose-600" /> Reject
                      </button>
                      <button
                        onClick={() => approveMutation.mutate(req.name)}
                        disabled={approveMutation.isPending}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-[11px] font-bold text-white shadow-xs hover:bg-indigo-700 disabled:opacity-50"
                      >
                        <Check className="h-3.5 w-3.5" /> Approve
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Team Exceptions List */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Team Attendance Exceptions</h3>
            <p className="text-xs text-slate-500">Missing checkouts and late arrivals flagged for today</p>
          </div>
        </div>

        {loadingExceptions ? (
          <LoadingSkeleton rows={4} height="h-10" />
        ) : !exceptions?.records || exceptions.records.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            No attendance exceptions recorded for your team on this date.
          </div>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="w-full text-left text-xs min-w-[550px]">
              <thead>
                <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase">
                  <th className="py-2.5 px-4 sm:px-0">Employee</th>
                  <th className="py-2.5 px-4 sm:px-0">Department</th>
                  <th className="py-2.5 px-4 sm:px-0">Exception Type</th>
                  <th className="py-2.5 px-4 sm:px-0">Date</th>
                  <th className="py-2.5 px-4 sm:px-0">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {exceptions.records.map((exc) => (
                  <tr key={exc.name} className="hover:bg-slate-50/50">
                    <td className="py-2.5 px-4 sm:px-0 font-medium text-slate-900">{exc.employee_name || exc.employee}</td>
                    <td className="py-2.5 px-4 sm:px-0 text-slate-600">{exc.department || '—'}</td>
                    <td className="py-2.5 px-4 sm:px-0">
                      <span className="inline-flex items-center gap-1 text-amber-700 font-medium">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {exc.exception_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 sm:px-0 text-slate-500 whitespace-nowrap">{formatDate(exc.activity_date)}</td>
                    <td className="py-2.5 px-4 sm:px-0">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
                        {exc.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
