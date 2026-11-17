import React from 'react';
import type { AttendanceStatus } from '../../types';
import { STATUS_CONFIG } from '../../utils/constants';

interface StatusBadgeProps {
  status: AttendanceStatus | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const config = STATUS_CONFIG[status as AttendanceStatus] || {
    label: status,
    bg: 'bg-slate-100 border-slate-200 text-slate-700',
    dot: 'bg-slate-400'
  };

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs font-medium';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${config.bg} ${sizeClasses}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
};
