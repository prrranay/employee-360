import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, ArrowRight } from 'lucide-react';
import { managerApi, employeeApi } from '../../api/client';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { Pagination } from '../../components/common/Pagination';
import { formatDate } from '../../utils/formatters';

export const TeamPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const managerId = searchParams.get('manager_id') || undefined;

  const [searchTerm, setSearchTerm] = useState('');
  const [includeIndirect, setIncludeIndirect] = useState(1);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { data: managerProfile } = useQuery({
    queryKey: ['employeeProfile', managerId],
    queryFn: () => (managerId ? employeeApi.getProfile(managerId) : null),
    enabled: !!managerId
  });

  const { data: team, isLoading, error } = useQuery({
    queryKey: ['managerTeam', includeIndirect, managerId],
    queryFn: () => managerApi.getManagerTeam(includeIndirect, managerId)
  });

  const filtered = (team || []).filter((emp) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      emp.employee_name.toLowerCase().includes(term) ||
      emp.employee_id.toLowerCase().includes(term) ||
      emp.department.toLowerCase().includes(term)
    );
  });

  // Calculate pagination window
  const totalRecords = filtered.length;
  const totalPages = Math.ceil(totalRecords / pageSize);
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const handleSearchChange = (val: string) => {
    setSearchTerm(val);
    setPage(1);
  };

  const handleIndirectToggle = (val: number) => {
    setIncludeIndirect(val);
    setPage(1);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight">
              {managerProfile ? `${managerProfile.employee_name}'s Team Roster` : 'Team Roster & Hierarchy'}
            </h2>
            {managerId && (
              <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-xs font-bold text-indigo-700">
                {managerId}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {managerProfile
              ? `Reporting line under ${managerProfile.employee_name} (${managerProfile.designation} • ${managerProfile.department}) — ${totalRecords.toLocaleString()} members`
              : `Direct and indirect reports under your management chain (${totalRecords.toLocaleString()} members)`}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {managerId && (
            <button
              onClick={() => {
                searchParams.delete('manager_id');
                setSearchParams(searchParams);
                setPage(1);
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition"
            >
              Reset to My Team
            </button>
          )}

          <div className="flex items-center gap-1 sm:gap-2 rounded-xl border border-slate-200 bg-white p-1 text-xs shadow-xs w-full sm:w-auto">
            <button
              onClick={() => handleIndirectToggle(1)}
              className={`flex-1 sm:flex-initial rounded-lg px-2.5 sm:px-3 py-1.5 font-semibold text-center transition ${
                includeIndirect === 1
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Reports
            </button>
            <button
              onClick={() => handleIndirectToggle(0)}
              className={`flex-1 sm:flex-initial rounded-lg px-2.5 sm:px-3 py-1.5 font-semibold text-center transition ${
                includeIndirect === 0
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Direct Only
            </button>
          </div>
        </div>
      </div>

      {/* Search & Page Size Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 sm:gap-4 rounded-2xl border border-slate-200/90 bg-white p-3 sm:p-4 shadow-xs">
        <div className="relative w-full sm:max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Filter team members by name, ID, or department..."
            className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-xs placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-600 justify-end sm:justify-start">
          <span>Rows per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:outline-none"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      {/* Team Table */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <LoadingSkeleton rows={6} height="h-12" />
        ) : error ? (
          <ErrorState message="Could not load team members." />
        ) : paginated.length === 0 ? (
          <EmptyState
            title="No team members found"
            message="No employees match your search criteria or report to your account."
          />
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[650px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4 sm:px-6">Employee ID</th>
                    <th className="py-3 px-4 sm:px-6">Name</th>
                    <th className="py-3 px-4 sm:px-6">Department</th>
                    <th className="py-3 px-4 sm:px-6">Designation</th>
                    <th className="py-3 px-4 sm:px-6">Joining Date</th>
                    <th className="py-3 px-4 sm:px-6 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginated.map((emp) => (
                    <tr
                      key={emp.employee_id}
                      onClick={() => navigate(`/employees/${emp.employee_id}`)}
                      className="cursor-pointer hover:bg-indigo-50/30 transition-colors"
                    >
                      <td className="py-3.5 px-4 sm:px-6 font-mono font-medium text-slate-700 whitespace-nowrap">{emp.employee_id}</td>
                      <td className="py-3.5 px-4 sm:px-6 font-semibold text-slate-900 whitespace-nowrap">{emp.employee_name}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{emp.department}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-600 whitespace-nowrap">{emp.designation}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-slate-500 whitespace-nowrap">{formatDate(emp.date_of_joining)}</td>
                      <td className="py-3.5 px-4 sm:px-6 text-right whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800">
                          View Profile <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              totalRecords={totalRecords}
              pageSize={pageSize}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
};
