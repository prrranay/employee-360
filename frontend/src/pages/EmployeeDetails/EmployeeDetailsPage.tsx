import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Building,
  Briefcase,
  Calendar,
  Clock,
  CheckCircle2,
  Percent,
  CalendarOff
} from 'lucide-react';
import { employeeApi } from '../../api/client';
import { KpiCard } from '../../components/common/KpiCard';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Pagination } from '../../components/common/Pagination';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { formatDate, formatTime, formatSecondsToHours } from '../../utils/formatters';

export const EmployeeDetailsPage: React.FC = () => {
  const { employeeId } = useParams<{ employeeId: string }>();
  const navigate = useNavigate();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const pageSize = 20;

  const empId = employeeId || 'EMP-00001';

  const { data: profile, isLoading: loadingProfile, error: errProfile } = useQuery({
    queryKey: ['employeeProfile', empId],
    queryFn: () => employeeApi.getProfile(empId)
  });

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['employeeSummary', empId],
    queryFn: () => employeeApi.getSummary(empId)
  });

  const { data: activityData, isLoading: loadingActivity } = useQuery({
    queryKey: ['employeeActivity', empId, page, statusFilter],
    queryFn: () =>
      employeeApi.getActivity(empId, undefined, undefined, statusFilter || undefined, page, pageSize)
  });

  if (errProfile) {
    return <ErrorState message={`Could not load profile for employee ${empId}.`} />;
  }

  return (
    <div className="space-y-6">
      {/* Top Back Navigation */}
      <div>
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeft className="h-4 w-4" /> Back to workforce
        </button>
      </div>

      {/* Employee Profile Header Card */}
      {loadingProfile ? (
        <LoadingSkeleton rows={2} height="h-20" />
      ) : (
        <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600 text-xl font-bold text-white shadow-sm">
                {(profile?.employee_name || 'E').charAt(0)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                    {profile?.employee_name}
                  </h2>
                  <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-slate-700">
                    {profile?.employee_id}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Briefcase className="h-3.5 w-3.5 text-slate-400" />
                    {profile?.designation}
                  </span>
                  <span className="flex items-center gap-1">
                    <Building className="h-3.5 w-3.5 text-slate-400" />
                    {profile?.department}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5 text-slate-400" />
                    Joined: {formatDate(profile?.date_of_joining)}
                  </span>
                </div>
              </div>
            </div>

            {/* Manager and Shift Details */}
            <div className="flex flex-col sm:flex-row gap-3 border-t md:border-t-0 md:border-l border-slate-100 pt-3 md:pt-0 md:pl-6 text-xs">
              <div>
                <span className="text-slate-400 font-medium">Reporting Manager</span>
                <p className="font-semibold text-slate-800 mt-0.5">
                  {profile?.manager_name ? `${profile.manager_name} (${profile.manager})` : 'Executive / None'}
                </p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Shift Assignment</span>
                <p className="font-semibold text-slate-800 mt-0.5">{profile?.shift || 'General Shift'}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards Summary */}
      {loadingSummary ? (
        <LoadingSkeleton rows={1} height="h-24" />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            title="Attendance Rate"
            value={`${summary?.attendance_percentage || 0}%`}
            subtitle="Annual rate (365 days)"
            icon={Percent}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Days Present"
            value={summary?.present_count.toLocaleString() || '0'}
            subtitle="On-time attendance"
            icon={CheckCircle2}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Late Days"
            value={summary?.late_count.toLocaleString() || '0'}
            subtitle="Past 15m grace"
            icon={Clock}
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
          />
          <KpiCard
            title="Avg Daily Work"
            value={summary?.avg_daily_work_formatted || '0h 0m'}
            subtitle="Completed sessions only"
            icon={CalendarOff}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
          />
        </div>
      )}

      {/* Historical Attendance Table */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Historical Attendance Summary</h3>
            <p className="text-xs text-slate-500">Every daily summary record across 365 calendar dates</p>
          </div>
          <div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="Present">Present</option>
              <option value="Late">Late</option>
              <option value="Half Day">Half Day</option>
              <option value="Absent">Absent</option>
              <option value="On Leave">On Leave</option>
              <option value="Weekly Off">Weekly Off</option>
              <option value="Missing Check-out">Missing Check-out</option>
            </select>
          </div>
        </div>

        {loadingActivity ? (
          <LoadingSkeleton rows={6} height="h-10" />
        ) : !activityData?.records || activityData.records.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-400">
            No activity records found matching criteria.
          </div>
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-6">Date</th>
                    <th className="py-3 px-6">Status</th>
                    <th className="py-3 px-6">First Login</th>
                    <th className="py-3 px-6">Last Logout</th>
                    <th className="py-3 px-6">Work Duration</th>
                    <th className="py-3 px-6">Sessions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activityData.records.map((log) => (
                    <tr key={log.name} className="hover:bg-slate-50/50">
                      <td className="py-3 px-6 font-medium text-slate-900">{formatDate(log.activity_date)}</td>
                      <td className="py-3 px-6">
                        <StatusBadge status={log.attendance_status} size="sm" />
                      </td>
                      <td className="py-3 px-6 text-slate-600">{formatTime(log.first_login)}</td>
                      <td className="py-3 px-6 text-slate-600">{formatTime(log.last_logout)}</td>
                      <td className="py-3 px-6 font-semibold text-slate-800">
                        {formatSecondsToHours(log.total_work_seconds)}
                      </td>
                      <td className="py-3 px-6 text-slate-600">{log.total_sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={page}
              totalPages={activityData.total_pages}
              totalRecords={activityData.total}
              pageSize={pageSize}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
};
