import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, Calendar, ChevronDown, Menu } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { SearchAutocomplete } from '../components/common/SearchAutocomplete';
import type { Employee } from '../types';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { user, isCeo, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const emp = user?.employee;
  const todayStr = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectEmployee = (selectedEmp: Employee) => {
    navigate(`/employees/${selectedEmp.employee_id}`);
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-4 sm:px-6 lg:px-8 backdrop-blur-xs">
      <div className="flex items-center gap-2 sm:gap-4 flex-1 max-w-xl">
        {/* Mobile Hamburger Toggle Button */}
        <button
          type="button"
          onClick={onToggleSidebar}
          className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none lg:hidden shrink-0"
          aria-label="Toggle navigation drawer"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Autocomplete for CEO or General Search */}
        {isCeo && (
          <div className="flex-1 max-w-md">
            <SearchAutocomplete
              onSelectEmployee={handleSelectEmployee}
              placeholder="Search 30,000 employees..."
            />
          </div>
        )}
      </div>

      {/* Right Action Cluster */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {/* Date Display (Hidden on very small screens, visible on sm and up) */}
        <div className="hidden sm:flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600">
          <Calendar className="h-3.5 w-3.5 text-slate-400" />
          <span>{todayStr}</span>
        </div>

        {/* User Profile Menu */}
        <div ref={menuRef} className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2 rounded-xl border border-slate-200/80 p-1 sm:p-1.5 sm:pr-3 text-left transition hover:bg-slate-50 focus:outline-none"
            aria-label="User profile menu"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-xs font-bold text-white shadow-xs shrink-0">
              {(emp?.employee_name || 'U').charAt(0)}
            </div>
            <div className="hidden md:block">
              <div className="text-xs font-bold text-slate-900 leading-tight">
                {emp?.employee_name || user?.user_id}
              </div>
              <div className="text-[10px] text-slate-400 leading-tight">
                {emp?.designation || 'Active Session'}
              </div>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-slate-400 hidden sm:block" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl z-50">
              <div className="border-b border-slate-100 px-3 py-2 text-xs">
                <p className="font-semibold text-slate-900 truncate">{emp?.employee_name}</p>
                <p className="text-[11px] text-slate-500 truncate">{user?.user_id}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
                    {emp?.employee_id || 'ID'}
                  </span>
                  {emp?.department && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 truncate max-w-[120px]">
                      {emp.department}
                    </span>
                  )}
                </div>
              </div>

              <button
                onClick={logout}
                className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-rose-600 transition hover:bg-rose-50"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
