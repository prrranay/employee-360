import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  CalendarCheck,
  UserCheck,
  CalendarDays,
  AlertTriangle,
  Building2,
  ShieldCheck
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export const Sidebar: React.FC = () => {
  const { isCeo, isManager, roles } = useAuth();

  const navItems = [
    {
      to: '/dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      show: true
    },
    {
      to: '/my-attendance',
      label: 'My Attendance',
      icon: CalendarCheck,
      show: true
    },
    {
      to: '/employees',
      label: 'Employees',
      icon: Users,
      show: isCeo
    },
    {
      to: '/team',
      label: 'Team Directory',
      icon: UserCheck,
      show: isManager
    },
    {
      to: '/leave',
      label: 'Leave Management',
      icon: CalendarDays,
      show: true
    },
    {
      to: '/attendance-exceptions',
      label: 'Exceptions',
      icon: AlertTriangle,
      show: isManager || isCeo
    }
  ];

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-200 bg-white">
      {/* Brand Header */}
      <div className="flex h-16 items-center gap-3 border-b border-slate-100 px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 text-white shadow-sm">
          <Building2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-slate-900 tracking-tight">Employee360</h1>
          <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Enterprise Suite</p>
        </div>
      </div>

      {/* Role Pill */}
      <div className="px-6 py-3 border-b border-slate-50">
        <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <ShieldCheck className="h-3.5 w-3.5 text-indigo-600" />
            {isCeo ? 'CEO Admin' : isManager ? 'Team Manager' : 'Employee'}
          </span>
          <span className="rounded bg-indigo-100/80 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700">
            {roles[0] || 'Active'}
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-4">
        {navItems
          .filter((item) => item.show)
          .map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700 font-bold shadow-xs'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            );
          })}
      </nav>

      {/* Footer Branding */}
      <div className="border-t border-slate-100 p-4">
        <div className="rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500">
          <div className="font-semibold text-slate-700">Dataset Scale</div>
          <div className="text-[10px] mt-0.5 text-slate-400">30,000 Employees | 10.95M Logs</div>
        </div>
      </div>
    </aside>
  );
};
