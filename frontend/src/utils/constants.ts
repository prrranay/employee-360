import type { AttendanceStatus } from '../types';

export const STATUS_CONFIG: Record<AttendanceStatus, { label: string; bg: string; text: string; dot: string }> = {
  'Present': {
    label: 'Present',
    bg: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500'
  },
  'Late': {
    label: 'Late Arrival',
    bg: 'bg-amber-50 border-amber-200 text-amber-700',
    text: 'text-amber-700',
    dot: 'bg-amber-500'
  },
  'Half Day': {
    label: 'Half Day',
    bg: 'bg-blue-50 border-blue-200 text-blue-700',
    text: 'text-blue-700',
    dot: 'bg-blue-500'
  },
  'Absent': {
    label: 'Absent',
    bg: 'bg-rose-50 border-rose-200 text-rose-700',
    text: 'text-rose-700',
    dot: 'bg-rose-500'
  },
  'On Leave': {
    label: 'On Leave',
    bg: 'bg-purple-50 border-purple-200 text-purple-700',
    text: 'text-purple-700',
    dot: 'bg-purple-500'
  },
  'Weekly Off': {
    label: 'Weekly Off',
    bg: 'bg-slate-100 border-slate-200 text-slate-600',
    text: 'text-slate-600',
    dot: 'bg-slate-400'
  },
  'Holiday': {
    label: 'Holiday',
    bg: 'bg-indigo-50 border-indigo-200 text-indigo-700',
    text: 'text-indigo-700',
    dot: 'bg-indigo-500'
  },
  'Missing Check-out': {
    label: 'Missing Check-out',
    bg: 'bg-orange-50 border-orange-200 text-orange-700',
    text: 'text-orange-700',
    dot: 'bg-orange-500'
  },
  'Pending Review': {
    label: 'Pending Review',
    bg: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    text: 'text-yellow-700',
    dot: 'bg-yellow-500'
  }
};
