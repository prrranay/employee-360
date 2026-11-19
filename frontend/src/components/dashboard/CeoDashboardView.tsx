import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  CheckCircle,
  Clock,
  UserX,
  CalendarOff,
  AlertOctagon,
  TrendingUp,
  Percent,
  Search,
  ArrowRight,
  Award
} from 'lucide-react';
import { ceoApi } from '../../api/client';
import { KpiCard } from '../common/KpiCard';
import { AttendanceTrendChart } from '../charts/AttendanceTrendChart';
import { DepartmentBreakdownChart } from '../charts/DepartmentBreakdownChart';
import { StatusDonutChart } from '../charts/StatusDonutChart';
import { LoadingSkeleton } from '../common/LoadingSkeleton';
import { ErrorState } from '../common/ErrorState';
import { Pagination } from '../common/Pagination';

export const CeoDashboardView: React.FC = () => {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState('2026-11-16');
  const [trendDays, setTrendDays] = useState<30 | 90 | 180 | 365>(30);
  const [managerSearch, setManagerSearch] = useState('');
  const [healthFilter, setHealthFilter] = useState<'ALL' | 'Excellent' | 'Good' | 'Needs Review'>('ALL');
  const [managerPage, setManagerPage] = useState(1);
  const managerPageSize = 8;

  const { data: summary, isLoading: loadingSummary, error: errSummary } = useQuery({
    queryKey: ['companySummary', selectedDate],
    queryFn: () => ceoApi.getCompanySummary(selectedDate)
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ['companyTrends', trendDays, selectedDate],
    queryFn: () => ceoApi.getCompanyAttendanceTrend(undefined, selectedDate, trendDays)
  });

  const { data: departments, isLoading: loadingDepts } = useQuery({
    queryKey: ['companyDepartments', selectedDate],
    queryFn: () => ceoApi.getDepartmentAnalytics(selectedDate)
  });

  // Manager Performance Query
  const { data: managerPerfData, isLoading: loadingPerf } = useQuery({
    queryKey: ['managerPerformance', selectedDate],
    queryFn: () => ceoApi.getManagerPerformance(selectedDate)
  });

  if (errSummary) {
    return <ErrorState message="Could not load company-wide summary data." />;
  }

  const donutData = summary
    ? [
        { name: 'Present', value: summary.present, color: '#10b981' },
        { name: 'Late', value: summary.late, color: '#f59e0b' },
        { name: 'Half Day', value: summary.half_day, color: '#3b82f6' },
        { name: 'Absent', value: summary.absent, color: '#f43f5e' },
        { name: 'On Leave', value: summary.on_leave, color: '#8b5cf6' },
        { name: 'Missing Out', value: summary.missing_checkout, color: '#ea580c' }
      ]
    : [];

  const allManagers = managerPerfData?.managers || [];
  const filteredManagers = allManagers.filter((m: any) => {
    if (healthFilter !== 'ALL' && m.performance_status !== healthFilter) {
      return false;
    }
    if (!managerSearch) return true;
    const term = managerSearch.toLowerCase();
    return (
      m.manager_name.toLowerCase().includes(term) ||
      m.manager_id.toLowerCase().includes(term) ||
      m.department.toLowerCase().includes(term) ||
      m.designation.toLowerCase().includes(term)
    );
  });

  const totalManagerRecords = filteredManagers.length;
  const totalManagerPages = Math.ceil(totalManagerRecords / managerPageSize);
  const paginatedManagers = filteredManagers.slice(
    (managerPage - 1) * managerPageSize,
    managerPage * managerPageSize
  );

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Top Banner & Date Selector */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">Executive Workforce Dashboard</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time analytics across 30,000 employees and 10.95M historical records
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

      {/* KPI Stat Cards */}
      {loadingSummary ? (
        <LoadingSkeleton rows={2} height="h-24" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <KpiCard
            title="Total Workforce"
            value={summary?.total_employees.toLocaleString() || '30,000'}
            subtitle="Active Personnel"
            icon={Users}
            iconBg="bg-indigo-50"
            iconColor="text-indigo-600"
          />
          <KpiCard
            title="Attendance Rate"
            value={`${summary?.attendance_rate || 0}%`}
            subtitle="Workable workforce attended"
            icon={Percent}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Present Today"
            value={summary?.present.toLocaleString() || '0'}
            subtitle="On-time arrivals"
            icon={CheckCircle}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <KpiCard
            title="Late Arrivals"
            value={summary?.late.toLocaleString() || '0'}
            subtitle="Past 15m grace period"
            icon={Clock}
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
          />
          <KpiCard
            title="Absent Today"
            value={summary?.absent.toLocaleString() || '0'}
            subtitle="Unexcused absences"
            icon={UserX}
            iconBg="bg-rose-50"
            iconColor="text-rose-600"
          />
          <KpiCard
            title="On Approved Leave"
            value={summary?.on_leave.toLocaleString() || '0'}
            subtitle="Scheduled time off"
            icon={CalendarOff}
            iconBg="bg-purple-50"
            iconColor="text-purple-600"
          />
          <KpiCard
            title="Missing Check-out"
            value={summary?.missing_checkout.toLocaleString() || '0'}
            subtitle="Incomplete punch sessions"
            icon={AlertOctagon}
            iconBg="bg-orange-50"
            iconColor="text-orange-600"
          />
          <KpiCard
            title="Avg Work Duration"
            value={summary?.avg_work_formatted || '0h 0m'}
            subtitle="Across completed sessions"
            icon={TrendingUp}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
          />
        </div>
      )}

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Attendance Trend Chart */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">{trendDays}-Day Attendance Trajectory</h3>
              <p className="text-xs text-slate-500">Aggregated daily headcounts by status over the selected window</p>
            </div>

            <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs">
              {([30, 90, 180, 365] as const).map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setTrendDays(days)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                    trendDays === days
                      ? 'bg-white text-indigo-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {days}D
                </button>
              ))}
            </div>
          </div>
          {loadingTrends ? (
            <LoadingSkeleton rows={4} height="h-16" />
          ) : (
            <AttendanceTrendChart data={trends || []} height={300} />
          )}
        </div>

        {/* Status Distribution Donut */}
        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900">Attendance Distribution</h3>
          <p className="text-xs text-slate-500 mb-2">Proportional status breakdown</p>
          {loadingSummary ? (
            <LoadingSkeleton rows={3} height="h-16" />
          ) : (
            <StatusDonutChart data={donutData} height={280} />
          )}
        </div>
      </div>

      {/* Department Analytics Section */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Department-wise Analytics</h3>
            <p className="text-xs text-slate-500">Attendance rate and headcount across business units</p>
          </div>
        </div>

        {loadingDepts ? (
          <LoadingSkeleton rows={5} height="h-10" />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8 items-center">
            <DepartmentBreakdownChart data={departments || []} height={320} />
            <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
              <table className="w-full text-left text-xs min-w-[320px]">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase">
                    <th className="py-2.5">Department</th>
                    <th className="py-2.5 text-right">Headcount</th>
                    <th className="py-2.5 text-right">Present</th>
                    <th className="py-2.5 text-right">Attendance Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {departments?.map((dept) => (
                    <tr key={dept.department} className="hover:bg-slate-50/50">
                      <td className="py-2 font-medium text-slate-900">{dept.department}</td>
                      <td className="py-2 text-right text-slate-600">{dept.total_headcount.toLocaleString()}</td>
                      <td className="py-2 text-right text-emerald-600 font-semibold">{dept.present_count.toLocaleString()}</td>
                      <td className="py-2 text-right font-bold text-slate-800">{dept.attendance_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* MANAGER PERFORMANCE & TEAM HEALTH TABLE */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Award className="h-4 w-4 text-indigo-600" />
              Manager Performance & Team Operations
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Comparative attendance rates, headcount, and punctuality across each manager's team on {selectedDate}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto">
            {/* Team Health Filter Pills */}
            <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs overflow-x-auto">
              <button
                type="button"
                onClick={() => {
                  setHealthFilter('ALL');
                  setManagerPage(1);
                }}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition shrink-0 ${
                  healthFilter === 'ALL'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All ({allManagers.length})
              </button>
              <button
                type="button"
                onClick={() => {
                  setHealthFilter('Excellent');
                  setManagerPage(1);
                }}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition shrink-0 ${
                  healthFilter === 'Excellent'
                    ? 'bg-white text-emerald-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Excellent
              </button>
              <button
                type="button"
                onClick={() => {
                  setHealthFilter('Good');
                  setManagerPage(1);
                }}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition shrink-0 ${
                  healthFilter === 'Good'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <span className="h-2 w-2 rounded-full bg-indigo-500" />
                Good
              </button>
              <button
                type="button"
                onClick={() => {
                  setHealthFilter('Needs Review');
                  setManagerPage(1);
                }}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition shrink-0 ${
                  healthFilter === 'Needs Review'
                    ? 'bg-white text-amber-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                Needs Review
              </button>
            </div>

            {/* Manager Search */}
            <div className="relative flex-1 sm:w-64">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={managerSearch}
                onChange={(e) => {
                  setManagerSearch(e.target.value);
                  setManagerPage(1);
                }}
                placeholder="Filter managers or departments..."
                className="w-full rounded-xl border border-slate-200 py-1.5 pl-8 pr-3 text-xs placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {loadingPerf ? (
          <LoadingSkeleton rows={5} height="h-12" />
        ) : paginatedManagers.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No manager records match your filter criteria.
          </div>
        ) : (
          <div>
            <div className="overflow-x-auto -mx-4 sm:mx-0">
              <table className="w-full text-left text-xs min-w-[700px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Manager</th>
                    <th className="py-3 px-4">Department & Role</th>
                    <th className="py-3 px-4 text-center">Team Size</th>
                    <th className="py-3 px-4">Team Attendance Rate</th>
                    <th className="py-3 px-4 text-center">Present / Late / Absent</th>
                    <th className="py-3 px-4 text-center">Avg Hours</th>
                    <th className="py-3 px-4 text-center">Team Health</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginatedManagers.map((m: any) => (
                    <tr
                      key={m.manager_id}
                      className="hover:bg-slate-50/50 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900">{m.manager_name}</div>
                        <div className="font-mono text-[11px] text-slate-400">{m.manager_id}</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-700">{m.department}</div>
                        <div className="text-[11px] text-slate-400">{m.designation}</div>
                      </td>
                      <td className="py-3 px-4 text-center font-semibold text-slate-800">
                        {m.team_size} members
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-20 sm:w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                m.attendance_rate >= 92
                                  ? 'bg-emerald-500'
                                  : m.attendance_rate >= 85
                                  ? 'bg-indigo-500'
                                  : 'bg-amber-500'
                              }`}
                              style={{ width: `${Math.min(100, m.attendance_rate)}%` }}
                            />
                          </div>
                          <span className="font-bold text-slate-900">{m.attendance_rate}%</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center whitespace-nowrap">
                        <span className="text-emerald-600 font-semibold">{m.present_count}</span>
                        <span className="text-slate-300 mx-1">/</span>
                        <span className="text-amber-600 font-semibold">{m.late_count}</span>
                        <span className="text-slate-300 mx-1">/</span>
                        <span className="text-rose-600 font-semibold">{m.absent_count}</span>
                      </td>
                      <td className="py-3 px-4 text-center font-medium text-slate-700 whitespace-nowrap">
                        {m.avg_work_formatted}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                            m.performance_status === 'Excellent'
                              ? 'bg-emerald-100 text-emerald-800'
                              : m.performance_status === 'Good'
                              ? 'bg-indigo-100 text-indigo-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {m.performance_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <button
                          onClick={() => navigate(`/team?manager_id=${m.manager_id}`)}
                          className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800"
                        >
                          View Team <ArrowRight className="h-3 w-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={managerPage}
              totalPages={totalManagerPages}
              totalRecords={totalManagerRecords}
              pageSize={managerPageSize}
              onPageChange={setManagerPage}
            />
          </div>
        )}
      </div>
    </div>
  );
};
