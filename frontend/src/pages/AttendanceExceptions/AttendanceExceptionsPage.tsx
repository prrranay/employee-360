import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, X, ShieldCheck } from 'lucide-react';
import { ceoApi, managerApi, attendanceApi } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { Pagination } from '../../components/common/Pagination';
import { formatDate } from '../../utils/formatters';

export const AttendanceExceptionsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { isCeo, isManager } = useAuth();
  const [selectedDate, setSelectedDate] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data: exceptions, isLoading } = useQuery({
    queryKey: ['exceptionsPage', selectedDate, statusFilter, page, isCeo],
    queryFn: () => {
      if (isCeo) {
        return ceoApi.getCompanyAttendanceExceptions(selectedDate || undefined, statusFilter || undefined, page, pageSize);
      } else {
        return managerApi.getTeamExceptions(selectedDate || undefined, statusFilter || undefined, page, pageSize, 1);
      }
    }
  });

  const approveMutation = useMutation({
    mutationFn: (exceptionId: string) => attendanceApi.approveException(exceptionId, isCeo ? 'Approved by CEO' : 'Approved by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptionsPage'] });
      queryClient.invalidateQueries({ queryKey: ['teamExceptions'] });
      queryClient.invalidateQueries({ queryKey: ['teamSummary'] });
      queryClient.invalidateQueries({ queryKey: ['companySummary'] });
      queryClient.invalidateQueries({ queryKey: ['pendingManagerRequests'] });
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (exceptionId: string) => attendanceApi.rejectException(exceptionId, isCeo ? 'Rejected by CEO' : 'Rejected by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exceptionsPage'] });
      queryClient.invalidateQueries({ queryKey: ['teamExceptions'] });
      queryClient.invalidateQueries({ queryKey: ['pendingManagerRequests'] });
    }
  });

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">Attendance Exceptions & Regularization</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          {isCeo
            ? 'Company-wide anomaly detection and employee attendance regularization requests'
            : 'Review attendance exceptions and regularization requests flagged for your team members'}
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 rounded-2xl border border-slate-200/90 bg-white p-3 sm:p-4 shadow-xs">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-slate-600 flex-1 sm:flex-initial">
            <span className="shrink-0">Date:</span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => {
                setSelectedDate(e.target.value);
                setPage(1);
              }}
              className="w-full sm:w-auto rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 focus:outline-none"
            />
          </div>
          {selectedDate && (
            <button
              onClick={() => setSelectedDate('')}
              className="text-xs text-indigo-600 hover:text-indigo-800"
            >
              Clear Date
            </button>
          )}
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
            <option value="">All Statuses</option>
            <option value="Open">Open</option>
            <option value="Pending Review">Pending Review</option>
            <option value="Resolved">Resolved</option>
            <option value="Ignored">Ignored</option>
          </select>
        </div>
      </div>

      {/* Exceptions Table */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <LoadingSkeleton rows={6} height="h-12" />
        ) : !exceptions?.records || exceptions.records.length === 0 ? (
          <EmptyState
            title="No exceptions flagged"
            message="There are no attendance exceptions found matching the current filters."
          />
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[750px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4 sm:px-6">Employee</th>
                    <th className="py-3 px-4 sm:px-6">Department</th>
                    <th className="py-3 px-4 sm:px-6">Date</th>
                    <th className="py-3 px-4 sm:px-6">Exception Type</th>
                    <th className="py-3 px-4 sm:px-6">Description</th>
                    <th className="py-3 px-4 sm:px-6">Assigned Manager</th>
                    <th className="py-3 px-4 sm:px-6">Status</th>
                    {(isManager || isCeo) && <th className="py-3 px-4 sm:px-6 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {exceptions.records.map((exc) => (
                    <tr key={exc.name} className="hover:bg-slate-50/50">
                      <td className="py-3.5 px-4 sm:px-6 font-semibold text-slate-900 whitespace-nowrap">
                        {exc.employee_name || exc.employee}
                      </td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{exc.department || '—'}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-500 whitespace-nowrap">{formatDate(exc.activity_date)}</td>
                      <td className="py-3.5 px-4 sm:px-6 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          {exc.exception_type}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-600 max-w-xs truncate">{exc.description || '—'}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{exc.manager_name || exc.assigned_manager || '—'}</td>
                      <td className="py-3.5 px-4 sm:px-6 whitespace-nowrap">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${
                            exc.status === 'Resolved'
                              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                              : exc.status === 'Pending Review'
                              ? 'bg-blue-50 border-blue-200 text-blue-700'
                              : 'bg-amber-50 border-amber-200 text-amber-700'
                          }`}
                        >
                          {exc.status}
                        </span>
                      </td>
                      {(isManager || isCeo) && (
                        <td className="py-3.5 px-4 sm:px-6 text-right whitespace-nowrap">
                          {exc.status !== 'Resolved' && exc.status !== 'Ignored' ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => approveMutation.mutate(exc.name)}
                                disabled={approveMutation.isPending}
                                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-emerald-700 disabled:opacity-50"
                                title="Approve & Regularize"
                              >
                                <Check className="h-3 w-3" />
                                Approve
                              </button>
                              <button
                                onClick={() => rejectMutation.mutate(exc.name)}
                                disabled={rejectMutation.isPending}
                                className="inline-flex items-center gap-1 rounded-lg bg-rose-50 border border-rose-200 px-2.5 py-1 text-[11px] font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                                title="Reject"
                              >
                                <X className="h-3 w-3" />
                                Reject
                              </button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-400 font-medium inline-flex items-center gap-1">
                              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                              Audit Logged
                            </span>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={page}
              totalPages={exceptions.total_pages}
              totalRecords={exceptions.total}
              pageSize={pageSize}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
};
