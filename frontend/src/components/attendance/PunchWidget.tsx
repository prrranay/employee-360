import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { LogIn, LogOut, CheckCircle2, AlertCircle, MapPin, ShieldAlert } from 'lucide-react';
import { attendanceApi } from '../../api/client';
import { formatTime } from '../../utils/formatters';
import { StatusBadge } from '../common/StatusBadge';

export const PunchWidget: React.FC = () => {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [gpsStatus, setGpsStatus] = useState<string | null>(null);

  const { data: today, isLoading } = useQuery({
    queryKey: ['todayAttendance'],
    queryFn: attendanceApi.getTodayAttendance,
    refetchInterval: 30000 // Refresh every 30s
  });

  const getCoordinates = async (): Promise<{ latitude?: number; longitude?: number; gps_accuracy?: number }> => {
    if (!('geolocation' in navigator)) {
      setGpsStatus('Geolocation not supported by browser; using verified network IP.');
      return {};
    }

    return new Promise((resolve) => {
      setGpsStatus('Requesting momentary location for attendance verification...');
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGpsStatus(null);
          resolve({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            gps_accuracy: pos.coords.accuracy
          });
        },
        (_err) => {
          // Graceful fallback when denied or timed out
          setGpsStatus('Location access not granted; punch recorded via verified server IP.');
          resolve({});
        },
        { timeout: 4000, enableHighAccuracy: true, maximumAge: 60000 }
      );
    });
  };

  const punchInMutation = useMutation({
    mutationFn: async () => {
      setErrorMsg(null);
      const coords = await getCoordinates();
      return attendanceApi.checkIn({
        ...coords,
        device_info: 'Web Portal'
      });
    },
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ['todayAttendance'] });
      queryClient.invalidateQueries({ queryKey: ['employeeActivity'] });
      queryClient.invalidateQueries({ queryKey: ['employeeSummary'] });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.message || err?.message || 'Check-in failed.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  });

  const punchOutMutation = useMutation({
    mutationFn: async () => {
      setErrorMsg(null);
      const coords = await getCoordinates();
      return attendanceApi.checkOut({
        ...coords,
        device_info: 'Web Portal'
      });
    },
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ['todayAttendance'] });
      queryClient.invalidateQueries({ queryKey: ['employeeActivity'] });
      queryClient.invalidateQueries({ queryKey: ['employeeSummary'] });
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.message || err?.message || 'Check-out failed.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  });

  if (isLoading) {
    return (
      <div className="h-44 w-full animate-pulse rounded-2xl bg-white border border-slate-200" />
    );
  }

  const isCheckedIn = today?.current_state === 'Checked In';

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-6 shadow-sm">
      {errorMsg && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs font-medium text-rose-700">
          <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {gpsStatus && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-blue-50 border border-blue-200 p-2.5 text-xs text-blue-700">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-blue-600" />
          <span>{gpsStatus}</span>
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 sm:gap-6">
        {/* Left Status Summary */}
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Live Attendance Status
            </span>
            {today?.attendance_status && (
              <StatusBadge status={today.attendance_status} size="sm" />
            )}
            {today?.is_regularized && (
              <span className="rounded-md bg-purple-50 border border-purple-200 px-2 py-0.5 text-[10px] font-bold text-purple-700">
                Regularized
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2 sm:gap-3 pt-1">
            <span className="text-2xl sm:text-3xl font-extrabold text-slate-900">
              {today?.total_work_formatted || '0h 0m'}
            </span>
            <span className="text-xs font-medium text-slate-500">logged today</span>
          </div>
          <p className="text-xs text-slate-500">
            {today?.total_sessions || 0} active punch sessions recorded
          </p>
        </div>

        {/* Center Punch Timing Details */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 rounded-xl bg-slate-50 p-3 sm:px-6">
          <div>
            <span className="text-[11px] font-medium text-slate-400">First In</span>
            <p className="text-xs font-bold text-slate-800">{formatTime(today?.first_login)}</p>
          </div>
          <div>
            <span className="text-[11px] font-medium text-slate-400">Last Out</span>
            <p className="text-xs font-bold text-slate-800">{formatTime(today?.last_logout)}</p>
          </div>
        </div>

        {/* Right Punch Button */}
        <div className="w-full md:w-auto">
          {isCheckedIn ? (
            <button
              onClick={() => punchOutMutation.mutate()}
              disabled={punchOutMutation.isPending}
              className="inline-flex w-full md:w-auto items-center justify-center gap-2 rounded-xl bg-rose-600 px-6 py-3 text-xs font-bold text-white shadow-sm transition hover:bg-rose-700 active:scale-98 disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" />
              {punchOutMutation.isPending ? 'Logging Out...' : 'Clock Out (End Session)'}
            </button>
          ) : (
            <button
              onClick={() => punchInMutation.mutate()}
              disabled={punchInMutation.isPending}
              className="inline-flex w-full md:w-auto items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700 active:scale-98 disabled:opacity-50"
            >
              <LogIn className="h-4 w-4" />
              {punchInMutation.isPending ? 'Logging In...' : 'Clock In (Start Work)'}
            </button>
          )}
        </div>
      </div>

      {/* Privacy note */}
      <div className="mt-4 flex items-center gap-1.5 text-[10px] sm:text-[11px] text-slate-400">
        <MapPin className="h-3 w-3 shrink-0" />
        <span>Location is only read momentarily during clock-in/out to verify presence. Continuous tracking is never enabled.</span>
      </div>

      {/* Today's Punch List */}
      {today?.punches && today.punches.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <span className="text-[10px] sm:text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Today's Punch History
          </span>
          <div className="mt-2 flex flex-wrap gap-1.5 sm:gap-2">
            {today.punches.map((p, idx) => (
              <span
                key={idx}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${
                  p.log_type === 'IN'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-slate-200 bg-slate-50 text-slate-700'
                }`}
              >
                {p.log_type === 'IN' ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600 shrink-0" />
                ) : (
                  <AlertCircle className="h-3 w-3 text-slate-500 shrink-0" />
                )}
                {p.log_type}: {formatTime(p.time)}
                {p.source === 'Admin Correction' && (
                  <span className="text-[9px] bg-indigo-100 text-indigo-700 px-1 rounded font-bold">Regularized</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
