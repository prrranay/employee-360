import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, ArrowRight } from 'lucide-react';
import { ceoApi } from '../../api/client';
import { Pagination } from '../../components/common/Pagination';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { useDebounce } from '../../hooks/useDebounce';

export const EmployeesPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const debouncedSearch = useDebounce(searchTerm, 300);

  const { data, isLoading, error } = useQuery({
    queryKey: ['employeesList', debouncedSearch, selectedDept, page],
    queryFn: () =>
      ceoApi.getEmployeeOverview(
        selectedDept || undefined,
        undefined,
        undefined,
        page,
        pageSize,
        debouncedSearch || undefined
      )
  });

  const paginated = data?.records || [];
  const totalRecords = data?.total || 0;
  const totalPages = data?.total_pages || 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Workforce Directory</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Browse and inspect 30,000 employees with instant profile drilldown
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name or employee ID..."
            className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-xs placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <select
            value={selectedDept}
            onChange={(e) => {
              setSelectedDept(e.target.value);
              setPage(1);
            }}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 focus:border-indigo-500 focus:outline-none"
          >
            <option value="">All Departments</option>
            <option value="Engineering">Engineering</option>
            <option value="Sales">Sales</option>
            <option value="Product">Product</option>
            <option value="Marketing">Marketing</option>
            <option value="Finance">Finance</option>
            <option value="Human Resources">Human Resources</option>
            <option value="Operations">Operations</option>
            <option value="Customer Success">Customer Success</option>
            <option value="IT Support">IT Support</option>
            <option value="Legal">Legal</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
        {isLoading ? (
          <LoadingSkeleton rows={8} height="h-12" />
        ) : error ? (
          <ErrorState message="Could not load employee directory." />
        ) : paginated.length === 0 ? (
          <EmptyState title="No employees found" message="Try adjusting your search or department filter." />
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/60 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-6">Employee ID</th>
                    <th className="py-3 px-6">Name</th>
                    <th className="py-3 px-6">Department</th>
                    <th className="py-3 px-6">Designation</th>
                    <th className="py-3 px-6">Status</th>
                    <th className="py-3 px-6 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginated.map((emp) => (
                    <tr
                      key={emp.employee_id}
                      onClick={() => navigate(`/employees/${emp.employee_id}`)}
                      className="cursor-pointer hover:bg-indigo-50/30 transition-colors"
                    >
                      <td className="py-3.5 px-6 font-mono font-medium text-slate-700">{emp.employee_id}</td>
                      <td className="py-3.5 px-6 font-semibold text-slate-900">{emp.employee_name}</td>
                      <td className="py-3.5 px-6 text-slate-600">{emp.department}</td>
                      <td className="py-3.5 px-6 text-slate-600">{emp.designation}</td>
                      <td className="py-3.5 px-6">
                        <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700">
                          {emp.employment_status || 'Active'}
                        </span>
                      </td>
                      <td className="py-3.5 px-6 text-right">
                        <span className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800">
                          View 360 <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

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
