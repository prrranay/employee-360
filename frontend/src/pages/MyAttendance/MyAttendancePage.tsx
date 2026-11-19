import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Calendar as CalendarIcon, List } from 'lucide-react';
import { employeeApi } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { PunchWidget } from '../../components/attendance/PunchWidget';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Pagination } from '../../components/common/Pagination';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { CorrectionModal } from '../../components/attendance/CorrectionModal';
import { AttendanceCalendarView } from '../../components/attendance/AttendanceCalendarView';
import { formatDate, formatTime, formatSecondsToHours } from '../../utils/formatters';

export const MyAttendancePage: React.FC = () => {
  const { user } = useAuth();
  const empId = user?.employee?.employee_id || 'EMP-01362';

  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [correctionModalOpen, setCorrectionModalOpen] = useState(false);
  const [selectedCorrectionDate, setSelectedCorrectionDate] = useState('');
  const pageSize = 20;

  const { data: activityData, isLoading } = useQuery({
    queryKey: ['myActivity', empId, page, statusFilter, fromDate, toDate],
    queryFn: () =>
      employeeApi.getActivity(
        empId,
        fromDate || undefined,
        toDate || undefined,
        statusFilter || undefined,
        page,
        pageSize
      ),
    enabled: viewMode === 'list'
  });

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">My Attendance Portal</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Clock in/out, view daily logs, and submit correction requests
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* View Toggle: Calendar (Default) vs List */}
          <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs">
            <button
              type="button"
              onClick={() => setViewMode('calendar')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-semibold transition ${
                viewMode === 'calendar'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <CalendarIcon className="h-3.5 w-3.5" />
              Calendar View
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-semibold transition ${
                viewMode === 'list'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <List className="h-3.5 w-3.5" />
              List View
            </button>
          </div>

          <button
            onClick={() => {
              setSelectedCorrectionDate('');
              setCorrectionModalOpen(true);
            }}
            className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
          >
            <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
            <span>Request Correction</span>
          </button>
        </div>
      </div>

      {/* Live Punch Widget */}
      <PunchWidget />

      {/* View Content: Calendar vs List */}
      {viewMode === 'calendar' ? (
        <AttendanceCalendarView
          employeeId={empId}
          onRequestCorrection={(date) => {
            setSelectedCorrectionDate(date);
            setCorrectionModalOpen(true);
          }}
        />
      ) : (
        <div className="space-y-4 sm:space-y-6">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 rounded-2xl border border-slate-200/90 bg-white p-3 sm:p-4 shadow-xs">
            <div className="flex flex-wrap items-center gap-2 sm:gap-3 w-full sm:w-auto">
              <div className="flex items-center gap-1.5 text-xs text-slate-600 flex-1 sm:flex-initial">
                <span className="shrink-0">From:</span>
                <input
                  type="date"
                  value={fromDate}
                  onChange={(e) => {
                    setFromDate(e.target.value);
                    setPage(1);
                  }}
                  className="w-full sm:w-auto rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-600 flex-1 sm:flex-initial">
                <span className="shrink-0">To:</span>
                <input
                  type="date"
                  value={toDate}
                  onChange={(e) => {
                    setToDate(e.target.value);
                    setPage(1);
                  }}
                  className="w-full sm:w-auto rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full sm:w-auto rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 focus:outline-none"
              >
                <option value="">All Attendance Statuses</option>
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

          {/* Paginated History Table */}
          <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
            {isLoading ? (
              <LoadingSkeleton rows={6} height="h-10" />
            ) : !activityData?.records || activityData.records.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-400">
                No attendance activity records found for this period.
              </div>
            ) : (
              <div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[600px]">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                        <th className="py-3 px-4 sm:px-6">Date</th>
                        <th className="py-3 px-4 sm:px-6">Status</th>
                        <th className="py-3 px-4 sm:px-6">First In</th>
                        <th className="py-3 px-4 sm:px-6">Last Out</th>
                        <th className="py-3 px-4 sm:px-6">Work Duration</th>
                        <th className="py-3 px-4 sm:px-6">Sessions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {activityData.records.map((log) => (
                        <tr key={log.name} className="hover:bg-slate-50/50">
                          <td className="py-3 px-4 sm:px-6 font-medium text-slate-900 whitespace-nowrap">{formatDate(log.activity_date)}</td>
                          <td className="py-3 px-4 sm:px-6 whitespace-nowrap">
                            <StatusBadge status={log.attendance_status} size="sm" />
                          </td>
                          <td className="py-3 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{formatTime(log.first_login)}</td>
                          <td className="py-3 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{formatTime(log.last_logout)}</td>
                          <td className="py-3 px-4 sm:px-6 font-semibold text-slate-800 whitespace-nowrap">
                            {formatSecondsToHours(log.total_work_seconds)}
                          </td>
                          <td className="py-3 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{log.total_sessions}</td>
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
      )}

      <CorrectionModal
        isOpen={correctionModalOpen}
        onClose={() => setCorrectionModalOpen(false)}
        defaultDate={selectedCorrectionDate}
      />
    </div>
  );
};
