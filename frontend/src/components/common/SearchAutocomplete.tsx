import React, { useState, useEffect, useRef } from 'react';
import { Search, Loader2, User, Building, Briefcase } from 'lucide-react';
import { useDebounce } from '../../hooks/useDebounce';
import { ceoApi } from '../../api/client';
import type { Employee } from '../../types';

interface SearchAutocompleteProps {
  onSelectEmployee: (employee: Employee) => void;
  placeholder?: string;
}

export const SearchAutocomplete: React.FC<SearchAutocompleteProps> = ({
  onSelectEmployee,
  placeholder = 'Search by employee name or ID (e.g. EMP-00012)...'
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Employee[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    let active = true;

    async function fetchEmployees() {
      if (!debouncedQuery || debouncedQuery.trim().length < 2) {
        setResults([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const data = await ceoApi.searchEmployees(debouncedQuery.trim(), 10);
        if (active) {
          setResults(data || []);
          setIsOpen(true);
        }
      } catch {
        if (active) setResults([]);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    fetchEmployees();
    return () => {
      active = false;
    };
  }, [debouncedQuery]);

  // Click outside listener
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (emp: Employee) => {
    setQuery(`${emp.employee_name} (${emp.employee_id})`);
    setIsOpen(false);
    onSelectEmployee(emp);
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          placeholder={placeholder}
          className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-9 text-xs shadow-xs transition placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
        {isLoading && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate-400" />
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute left-0 right-0 z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
          {results.map((emp) => (
            <button
              key={emp.employee_id}
              onClick={() => handleSelect(emp)}
              className="flex w-full items-start gap-2.5 sm:gap-3 rounded-lg px-2.5 sm:px-3 py-2 text-left transition hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
                <User className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate text-xs font-semibold text-slate-900">{emp.employee_name}</span>
                  <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                    {emp.employee_id}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 sm:gap-3 text-[11px] text-slate-500">
                  <span className="flex items-center gap-1 truncate">
                    <Briefcase className="h-3 w-3 shrink-0 text-slate-400" />
                    {emp.designation}
                  </span>
                  <span className="flex items-center gap-1 truncate">
                    <Building className="h-3 w-3 shrink-0 text-slate-400" />
                    {emp.department}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {isOpen && !isLoading && debouncedQuery.trim().length >= 2 && results.length === 0 && (
        <div className="absolute left-0 right-0 z-50 mt-1 w-full rounded-xl border border-slate-200 bg-white p-4 text-center text-xs text-slate-500 shadow-xl">
          No matching employees found for "{debouncedQuery}".
        </div>
      )}
    </div>
  );
};
