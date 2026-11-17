import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Calendar as CalendarIcon,
  X,
  FileEdit
} from 'lucide-react';
import { employeeApi } from '../../api/client';
import type { ActivityLogRecord } from '../../types';
import { formatTime, formatSecondsToHours, formatDate } from '../../utils/formatters';
import { StatusBadge } from '../common/StatusBadge';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

interface AttendanceCalendarViewProps {
  employeeId: string;
  onRequestCorrection?: (date: string) => void;
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const AttendanceCalendarView: React.FC<AttendanceCalendarViewProps> = ({
  employeeId,
  onRequestCorrection
}) => {
  // Default to November 2026 (matching system date 2026-11-17)
  const [currentYear, setCurrentYear] = useState(2026);
  const [currentMonth, setCurrentMonth] = useState(10); // 10 = November
  const [selectedRecord, setSelectedRecord] = useState<ActivityLogRecord | null>(null);

  // Calculate fromDate and toDate for the selected month
  const { fromDateStr, toDateStr, totalDaysInMonth, startDayOfWeek } = useMemo(() => {
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);

    const pad = (n: number) => String(n).padStart(2, '0');
    const fromStr = `${currentYear}-${pad(currentMonth + 1)}-01`;
    const toStr = `${currentYear}-${pad(currentMonth + 1)}-${pad(lastDay.getDate())}`;

    return {
      fromDateStr: fromStr,
      toDateStr: toStr,
      totalDaysInMonth: lastDay.getDate(),
      startDayOfWeek: firstDay.getDay()
    };
  }, [currentYear, currentMonth]);

  // Fetch month activity records
  const { data: activityData, isLoading } = useQuery({
    queryKey: ['employeeActivityCalendar', employeeId, fromDateStr, toDateStr],
    queryFn: () => employeeApi.getActivity(employeeId, fromDateStr, toDateStr, undefined, 1, 50)
  });

  // Map records by activity_date for fast lookup
  const recordsMap = useMemo(() => {
    const map = new Map<string, ActivityLogRecord>();
    if (activityData?.records) {
      activityData.records.forEach((rec) => {
        map.set(rec.activity_date, rec);
      });
    }
    return map;
  }, [activityData]);

  // Compute month summary metrics
  const monthStats = useMemo(() => {
    const stats = {
      present: 0,
      late: 0,
      halfDay: 0,
      absent: 0,
      onLeave: 0,
      weeklyOff: 0,
      missingCheckout: 0,
      totalSeconds: 0,
      workedDays: 0,
      avgSeconds: 0
    };

    if (activityData?.records) {
      activityData.records.forEach((rec) => {
        const sec = rec.total_work_seconds || 0;
        stats.totalSeconds += sec;
        if (sec > 0) {
          stats.workedDays++;
        }
        switch (rec.attendance_status) {
          case 'Present':
            stats.present++;
            break;
          case 'Late':
            stats.late++;
            break;
          case 'Half Day':
            stats.halfDay++;
            break;
          case 'Absent':
            stats.absent++;
            break;
          case 'On Leave':
            stats.onLeave++;
            break;
          case 'Weekly Off':
            stats.weeklyOff++;
            break;
          case 'Missing Check-out':
            stats.missingCheckout++;
            break;
        }
      });
      stats.avgSeconds = stats.workedDays > 0 ? Math.round(stats.totalSeconds / stats.workedDays) : 0;
    }
    return stats;
  }, [activityData]);

  const handlePrevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
    setSelectedRecord(null);
  };

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
    setSelectedRecord(null);
  };

  const handleTodayJump = () => {
    setCurrentYear(2026);
    setCurrentMonth(10);
    setSelectedRecord(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Present':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Late':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Half Day':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Absent':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'On Leave':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Weekly Off':
        return 'bg-slate-100 text-slate-500 border-slate-200';
      case 'Missing Check-out':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  // Build grid calendar cells
  const calendarCells = useMemo(() => {
    const cells = [];
    const pad = (n: number) => String(n).padStart(2, '0');

    // 1. Leading empty cells from previous month
    for (let i = 0; i < startDayOfWeek; i++) {
      cells.push({
        isPadding: true,
        dayNum: null,
        dateStr: ''
      });
    }

    // 2. Actual days of month
    for (let day = 1; day <= totalDaysInMonth; day++) {
      const dateStr = `${currentYear}-${pad(currentMonth + 1)}-${pad(day)}`;
      cells.push({
        isPadding: false,
        dayNum: day,
        dateStr,
        isToday: dateStr === '2026-11-17'
      });
    }

    return cells;
  }, [currentYear, currentMonth, startDayOfWeek, totalDaysInMonth]);

  return (
    <div className="space-y-6">
      {/* Month Navigation & Stats Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <CalendarIcon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">
              {MONTH_NAMES[currentMonth]} {currentYear}
            </h3>
            <p className="text-xs text-slate-500">
              {activityData?.records?.length || 0} recorded attendance logs in this month
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTodayJump}
            className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
          >
            Today (Nov 2026)
          </button>
          <div className="flex items-center rounded-xl border border-slate-200 bg-white p-0.5 shadow-xs">
            <button
              type="button"
              onClick={handlePrevMonth}
              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
              title="Previous Month"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 text-xs font-medium text-slate-400">|</span>
            <button
              type="button"
              onClick={handleNextMonth}
              className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
              title="Next Month"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Monthly Summary Statistics Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3">
          <div className="text-[11px] font-semibold text-emerald-800">Present</div>
          <div className="text-lg font-bold text-emerald-700 mt-0.5">{monthStats.present} days</div>
        </div>
        <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3">
          <div className="text-[11px] font-semibold text-amber-800">Late</div>
          <div className="text-lg font-bold text-amber-700 mt-0.5">{monthStats.late} days</div>
        </div>
        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-3">
          <div className="text-[11px] font-semibold text-blue-800">Half Day</div>
          <div className="text-lg font-bold text-blue-700 mt-0.5">{monthStats.halfDay} days</div>
        </div>
        <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-3">
          <div className="text-[11px] font-semibold text-rose-800">Absent</div>
          <div className="text-lg font-bold text-rose-700 mt-0.5">{monthStats.absent} days</div>
        </div>
        <div className="rounded-xl border border-purple-100 bg-purple-50/50 p-3">
          <div className="text-[11px] font-semibold text-purple-800">On Leave</div>
          <div className="text-lg font-bold text-purple-700 mt-0.5">{monthStats.onLeave} days</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="text-[11px] font-semibold text-slate-700">Weekly Off</div>
          <div className="text-lg font-bold text-slate-600 mt-0.5">{monthStats.weeklyOff} days</div>
        </div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 col-span-2 sm:col-span-1">
          <div className="text-[11px] font-semibold text-indigo-800">Avg Work Hours</div>
          <div className="text-lg font-bold text-indigo-700 mt-0.5">
            {formatSecondsToHours(monthStats.avgSeconds)}
          </div>
        </div>
      </div>

      {/* Interactive Calendar Grid */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs">
        {isLoading ? (
          <LoadingSkeleton rows={6} height="h-20" />
        ) : (
          <div>
            {/* Weekday headers */}
            <div className="grid grid-cols-7 gap-2 mb-2">
              {WEEKDAYS.map((day, idx) => (
                <div
                  key={day}
                  className={`py-2 text-center text-xs font-bold uppercase tracking-wider ${
                    idx === 0 || idx === 6 ? 'text-slate-400' : 'text-slate-600'
                  }`}
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-2">
              {calendarCells.map((cell, idx) => {
                if (cell.isPadding) {
                  return (
                    <div
                      key={`pad-${idx}`}
                      className="min-h-[105px] rounded-xl border border-dashed border-slate-100 bg-slate-50/40 p-2 opacity-40"
                    />
                  );
                }

                const rec = recordsMap.get(cell.dateStr);
                const isSelected = selectedRecord?.activity_date === cell.dateStr;

                return (
                  <div
                    key={cell.dateStr}
                    onClick={() => rec && setSelectedRecord(rec)}
                    className={`min-h-[105px] rounded-xl border p-2.5 transition flex flex-col justify-between ${
                      cell.isToday
                        ? 'border-indigo-400 bg-indigo-50/20 shadow-xs'
                        : isSelected
                        ? 'border-indigo-600 bg-indigo-50/30 ring-2 ring-indigo-500/20'
                        : rec
                        ? 'border-slate-200 bg-white hover:border-indigo-300 hover:shadow-xs cursor-pointer'
                        : 'border-slate-100 bg-slate-50/50'
                    }`}
                  >
                    {/* Top Row: Date & Today Pill */}
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-xs font-bold ${
                          cell.isToday
                            ? 'flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-white text-[11px]'
                            : rec
                            ? 'text-slate-800'
                            : 'text-slate-400'
                        }`}
                      >
                        {cell.dayNum}
                      </span>

                      {rec && rec.attendance_status && (
                        <span
                          className={`rounded-md border px-1.5 py-0.5 text-[10px] font-bold ${getStatusColor(
                            rec.attendance_status
                          )}`}
                        >
                          {rec.attendance_status}
                        </span>
                      )}
                    </div>

                    {/* Middle Info: Work Hours & Times */}
                    {rec ? (
                      <div className="mt-2 space-y-1">
                        {rec.total_work_seconds > 0 ? (
                          <>
                            <div className="text-[11px] font-bold text-slate-800 flex items-center gap-1">
                              <Clock className="h-3 w-3 text-slate-400" />
                              {formatSecondsToHours(rec.total_work_seconds)}
                            </div>
                            <div className="text-[10px] text-slate-500 truncate font-mono">
                              {formatTime(rec.first_login)} – {formatTime(rec.last_logout)}
                            </div>
                          </>
                        ) : (
                          <div className="text-[10px] text-slate-400 italic">
                            {rec.attendance_status === 'Weekly Off'
                              ? 'Scheduled Off'
                              : rec.attendance_status === 'On Leave'
                              ? 'Approved Leave'
                              : 'No punch logs'}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="mt-2 text-[10px] text-slate-300 italic">—</div>
                    )}

                    {/* Bottom Status Indicator */}
                    {rec && rec.total_sessions > 1 && (
                      <div className="mt-1 text-[9px] text-slate-400">
                        {rec.total_sessions} sessions
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Selected Day Inspector Panel */}
      {selectedRecord && (
        <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50/60 via-white to-indigo-50/30 p-5 shadow-xs transition animate-fadeIn">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <h4 className="text-sm font-bold text-slate-900">
                  {formatDate(selectedRecord.activity_date)}
                </h4>
                <StatusBadge status={selectedRecord.attendance_status} size="sm" />
              </div>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 pt-1">
                <div>
                  <span className="text-slate-400">First In: </span>
                  <span className="font-semibold text-slate-800">
                    {formatTime(selectedRecord.first_login)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Last Out: </span>
                  <span className="font-semibold text-slate-800">
                    {formatTime(selectedRecord.last_logout)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Duration: </span>
                  <span className="font-semibold text-indigo-700">
                    {formatSecondsToHours(selectedRecord.total_work_seconds)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Sessions: </span>
                  <span className="font-semibold text-slate-800">
                    {selectedRecord.total_sessions}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto">
              {onRequestCorrection && (
                <button
                  type="button"
                  onClick={() => onRequestCorrection(selectedRecord.activity_date)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 transition"
                >
                  <FileEdit className="h-3.5 w-3.5" />
                  Request Correction
                </button>
              )}
              <button
                type="button"
                onClick={() => setSelectedRecord(null)}
                className="rounded-xl border border-slate-200 bg-white p-2 text-slate-400 hover:text-slate-700 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 rounded-xl border border-slate-100 bg-slate-50/60 px-4 py-3">
        <span className="font-semibold text-slate-700">Status Legend:</span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> Present (On-time)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-amber-500" /> Late Arrival
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-blue-500" /> Half Day
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-rose-500" /> Absent
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-purple-500" /> On Leave
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-slate-400" /> Weekly Off
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-orange-500" /> Missing Check-out
        </span>
      </div>
    </div>
  );
};
