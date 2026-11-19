import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  iconBg?: string;
  iconColor?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  iconBg = 'bg-indigo-50',
  iconColor = 'text-indigo-600',
  trend
}) => {
  return (
    <div className="rounded-xl border border-slate-200/80 bg-white p-4 sm:p-5 shadow-sm transition-all hover:shadow-md">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-slate-500 truncate">{title}</span>
        <div className={`flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-lg ${iconBg} ${iconColor} shrink-0`}>
          <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
        </div>
      </div>
      <div className="mt-2.5 sm:mt-3 flex items-baseline gap-2">
        <span className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 truncate">{value}</span>
        {trend && (
          <span
            className={`text-xs font-medium shrink-0 ${
              trend.isPositive ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {trend.value}
          </span>
        )}
      </div>
      {subtitle && <p className="mt-1 text-[10px] sm:text-xs text-slate-500 truncate">{subtitle}</p>}
    </div>
  );
};
