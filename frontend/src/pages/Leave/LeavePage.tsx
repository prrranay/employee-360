import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FilePlus, Check, X, Calendar, Clock, Trash2 } from 'lucide-react';
import { managerApi, employeeApi } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { LeaveApplyModal } from '../../components/leave/LeaveApplyModal';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { Pagination } from '../../components/common/Pagination';
import { formatDate } from '../../utils/formatters';

export const LeavePage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user, isManager, isCeo } = useAuth();
  const empId = user?.employee?.employee_id || 'EMP-01362';

  const [applyModalOpen, setApplyModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'team' | 'calendar' | 'personal'>(isManager || isCeo ? 'team' : 'personal');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  // Leave Balances for Current Employee
  const { data: balances, isLoading: loadingBalances } = useQuery({
    queryKey: ['leaveBalance', empId],
    queryFn: () => employeeApi.getLeaveBalance(empId)
  });

  // Manager: Team Leaves Table
  const { data: teamLeaves, isLoading: loadingTeam } = useQuery({
    queryKey: ['teamLeaves', page],
    queryFn: () => managerApi.getTeamLeaves(undefined, page, pageSize),
    enabled: (isManager || isCeo) && activeTab === 'team'
  });

  // Manager: Team Leave Calendar Schedule
  const { data: calendarEvents, isLoading: loadingCalendar } = useQuery({
    queryKey: ['teamLeaveCalendar'],
    queryFn: () => managerApi.getTeamLeaveCalendar(),
    enabled: (isManager || isCeo) && activeTab === 'calendar'
  });

  // Employee: Personal Leaves
  const { data: personalLeaves, isLoading: loadingPersonal } = useQuery({
    queryKey: ['personalLeaves', empId, page],
    queryFn: () => employeeApi.getLeaveHistory(empId, page, pageSize),
    enabled: activeTab === 'personal'
  });

  const approveMutation = useMutation({
    mutationFn: (leaveId: string) => managerApi.approveLeave(leaveId, isCeo ? 'Approved by CEO' : 'Approved by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['teamLeaveCalendar'] });
      queryClient.invalidateQueries({ queryKey: ['leaveBalance'] });
      queryClient.invalidateQueries({ queryKey: ['pendingManagerRequests'] });
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (leaveId: string) => managerApi.rejectLeave(leaveId, isCeo ? 'Rejected by CEO' : 'Rejected by Manager'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teamLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['teamLeaveCalendar'] });
      queryClient.invalidateQueries({ queryKey: ['leaveBalance'] });
      queryClient.invalidateQueries({ queryKey: ['pendingManagerRequests'] });
    }
  });

  const cancelMutation = useMutation({
    mutationFn: (leaveId: string) => employeeApi.cancelLeave(leaveId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personalLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['leaveBalance'] });
      queryClient.invalidateQueries({ queryKey: ['teamLeaves'] });
      queryClient.invalidateQueries({ queryKey: ['teamLeaveCalendar'] });
    }
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Leave Management</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeTab === 'team'
              ? 'Review and manage team leave requests'
              : activeTab === 'calendar'
              ? 'Upcoming leave schedule across team reports'
              : 'Apply, view leave balance, and track your personal time-off requests'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {(isManager || isCeo) && (
            <div className="flex rounded-xl border border-slate-200 bg-white p-1 text-xs">
              <button
                onClick={() => {
                  setActiveTab('team');
                  setPage(1);
                }}
                className={`rounded-lg px-3 py-1.5 font-semibold transition ${
                  activeTab === 'team'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {isCeo ? 'Manager & Team Requests' : 'Team Requests'}
              </button>
              <button
                onClick={() => {
                  setActiveTab('calendar');
                }}
                className={`rounded-lg px-3 py-1.5 font-semibold transition ${
                  activeTab === 'calendar'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Team Calendar
              </button>
              <button
                onClick={() => {
                  setActiveTab('personal');
                  setPage(1);
                }}
                className={`rounded-lg px-3 py-1.5 font-semibold transition ${
                  activeTab === 'personal'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                My Applications
              </button>
            </div>
          )}

          <button
            onClick={() => setApplyModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-700 transition"
          >
            <FilePlus className="h-4 w-4" />
            Apply Leave
          </button>
        </div>
      </div>

      {/* Leave Balance Cards (Always visible on My Applications or for employees) */}
      {(!isManager && !isCeo || activeTab === 'personal') && (
        <div>
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Annual Leave Entitlement & Balance</h3>
          {loadingBalances ? (
            <LoadingSkeleton rows={1} height="h-24" />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {balances?.map((b) => (
                <div key={b.leave_type} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700">{b.leave_type}</span>
                    <span className="rounded-full bg-indigo-50 text-indigo-700 font-bold px-2 py-0.5 text-[10px]">
                      {b.remaining} left
                    </span>
                  </div>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-slate-900">{b.remaining}</span>
                    <span className="text-xs text-slate-400">/ {b.allocated} days</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-500">
                    <span>Used: <strong className="text-slate-700">{b.used}</strong></span>
                    <span>Pending: <strong className="text-amber-600">{b.pending}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Tab Content */}
      {activeTab === 'calendar' ? (
        /* Team Leave Calendar View */
        <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs p-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Team Leave Calendar Schedule</h3>
            </div>
            <span className="text-xs text-slate-500 font-medium">{calendarEvents?.length || 0} scheduled leaves</span>
          </div>

          {loadingCalendar ? (
            <LoadingSkeleton rows={5} height="h-12" />
          ) : !calendarEvents || calendarEvents.length === 0 ? (
            <EmptyState
              title="No upcoming team leaves"
              message="No team members currently have approved or pending leave scheduled in this period."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {calendarEvents.map((evt) => (
                <div key={evt.name} className="rounded-xl border border-slate-200 p-4 hover:shadow-sm transition bg-slate-50/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold text-slate-900">{evt.employee_name}</p>
                      <p className="text-[11px] text-slate-500">{evt.department} • {evt.employee}</p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                        evt.status === 'Approved'
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                          : 'bg-amber-50 border-amber-200 text-amber-700'
                      }`}
                    >
                      {evt.status}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center gap-1.5 text-xs text-indigo-700 font-semibold">
                    <Clock className="h-3.5 w-3.5" />
                    <span>{formatDate(evt.from_date)} – {formatDate(evt.to_date)}</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600 line-clamp-2">
                    <span className="font-medium text-slate-700">{evt.leave_type}:</span> {evt.reason}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Table Card (Team Requests or Personal Applications) */
        <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
          {((activeTab === 'team' && loadingTeam) || (activeTab === 'personal' && loadingPersonal)) ? (
            <LoadingSkeleton rows={6} height="h-12" />
          ) : !(activeTab === 'team' ? teamLeaves : personalLeaves)?.records ||
            (activeTab === 'team' ? teamLeaves : personalLeaves)!.records.length === 0 ? (
            <EmptyState
              title="No leave requests found"
              message={activeTab === 'team' ? 'No pending or historical leave applications from your team.' : 'You have not submitted any leave applications.'}
            />
          ) : (
            <div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                      {activeTab === 'team' && <th className="py-3 px-6">Employee</th>}
                      <th className="py-3 px-6">Leave Type</th>
                      <th className="py-3 px-6">Dates</th>
                      <th className="py-3 px-6">Reason</th>
                      <th className="py-3 px-6">Status</th>
                      <th className="py-3 px-6">Applied On</th>
                      <th className="py-3 px-6 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(activeTab === 'team' ? teamLeaves : personalLeaves)!.records.map((req) => (
                      <tr key={req.name} className="hover:bg-slate-50/50">
                        {activeTab === 'team' && (
                          <td className="py-3.5 px-6 font-semibold text-slate-900">
                            {req.employee_name || req.employee}
                            <div className="text-[10px] text-slate-400 font-normal">{req.department}</div>
                          </td>
                        )}
                        <td className="py-3.5 px-6 font-medium text-slate-800">{req.leave_type}</td>
                        <td className="py-3.5 px-6 text-slate-600 font-medium">
                          {formatDate(req.from_date)} – {formatDate(req.to_date)}
                        </td>
                        <td className="py-3.5 px-6 text-slate-600 max-w-xs truncate" title={req.reason}>{req.reason}</td>
                        <td className="py-3.5 px-6">
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${
                              req.status === 'Approved'
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                                : req.status === 'Rejected'
                                ? 'bg-rose-50 border-rose-200 text-rose-700'
                                : req.status === 'Cancelled'
                                ? 'bg-slate-100 border-slate-300 text-slate-600'
                                : 'bg-amber-50 border-amber-200 text-amber-700'
                            }`}
                          >
                            {req.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-6 text-slate-500">{formatDate(req.applied_at)}</td>
                        <td className="py-3.5 px-6 text-right">
                          {activeTab === 'team' ? (
                            req.status === 'Pending' ? (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => rejectMutation.mutate(req.name)}
                                  disabled={rejectMutation.isPending}
                                  className="rounded-lg border border-slate-300 p-1.5 text-rose-600 hover:bg-rose-50 transition"
                                  title="Reject"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => approveMutation.mutate(req.name)}
                                  disabled={approveMutation.isPending}
                                  className="rounded-lg bg-indigo-600 p-1.5 text-white shadow-xs hover:bg-indigo-700 transition"
                                  title="Approve"
                                >
                                  <Check className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <span className="text-slate-400 text-[11px]">—</span>
                            )
                          ) : (
                            /* Personal Applications Tab */
                            req.status === 'Pending' ? (
                              <button
                                onClick={() => cancelMutation.mutate(req.name)}
                                disabled={cancelMutation.isPending}
                                className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-100 transition"
                                title="Cancel pending application"
                              >
                                <Trash2 className="h-3 w-3" />
                                Cancel
                              </button>
                            ) : (
                              <span className="text-slate-400 text-[11px]">—</span>
                            )
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <Pagination
                currentPage={page}
                totalPages={(activeTab === 'team' ? teamLeaves : personalLeaves)!.total_pages}
                totalRecords={(activeTab === 'team' ? teamLeaves : personalLeaves)!.total}
                pageSize={pageSize}
                onPageChange={setPage}
              />
            </div>
          )}
        </div>
      )}

      <LeaveApplyModal
        isOpen={applyModalOpen}
        onClose={() => setApplyModalOpen(false)}
        employeeId={empId}
      />
    </div>
  );
};
