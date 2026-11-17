import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CeoDashboardView } from '../components/dashboard/CeoDashboardView';
import { ManagerDashboardView } from '../components/dashboard/ManagerDashboardView';
import { EmployeeDashboardView } from '../components/dashboard/EmployeeDashboardView';
import { AuthProvider } from '../hooks/useAuth';

// Mock API clients
vi.mock('../api/client', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn()
  },
  ceoApi: {
    getCompanySummary: vi.fn(),
    getCompanyAttendanceTrend: vi.fn(),
    getDepartmentAnalytics: vi.fn(),
    getManagerPerformance: vi.fn(),
    getPendingManagerRequests: vi.fn(),
    searchEmployees: vi.fn()
  },
  managerApi: {
    getTeamSummary: vi.fn(),
    getTeamAttendanceTrend: vi.fn(),
    getTeamLeaves: vi.fn(),
    getTeamExceptions: vi.fn(),
    approveLeave: vi.fn(),
    rejectLeave: vi.fn(),
    approveCorrection: vi.fn(),
    rejectCorrection: vi.fn()
  },
  employeeApi: {
    getSummary: vi.fn(),
    getTrend: vi.fn(),
    getProfile: vi.fn()
  },
  attendanceApi: {
    getTodayAttendance: vi.fn(),
    checkIn: vi.fn(),
    checkOut: vi.fn()
  }
}));

import { ceoApi, managerApi, employeeApi, attendanceApi, authApi } from '../api/client';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0
      }
    }
  });

describe('Dashboard Experiences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders CEO Dashboard with KPI metrics, attendance breakdown, and department analytics', async () => {
    vi.mocked(ceoApi.getCompanySummary).mockResolvedValueOnce({
      date: '2026-11-16',
      total_employees: 30000,
      present: 25420,
      late: 1205,
      half_day: 450,
      absent: 1540,
      on_leave: 885,
      weekly_off: 0,
      missing_checkout: 500,
      attendance_rate: 89.65,
      avg_work_seconds: 29800,
      avg_work_formatted: '8h 16m'
    });
    vi.mocked(ceoApi.getCompanyAttendanceTrend).mockResolvedValueOnce([]);
    vi.mocked(ceoApi.getDepartmentAnalytics).mockResolvedValueOnce([
      { department: 'Engineering', total_headcount: 12500, present_count: 11000, late_count: 500, half_day_count: 200, absent_count: 400, leave_count: 300, missing_checkout_count: 100, attendance_rate: 91.2, avg_work_formatted: '8h 22m' },
      { department: 'Sales', total_headcount: 8000, present_count: 7100, late_count: 300, half_day_count: 100, absent_count: 300, leave_count: 150, missing_checkout_count: 50, attendance_rate: 90.5, avg_work_formatted: '8h 15m' }
    ]);
    vi.mocked(ceoApi.getPendingManagerRequests).mockResolvedValueOnce({
      leaves: [],
      corrections: [],
      total_pending: 0
    });
    vi.mocked(ceoApi.getManagerPerformance).mockResolvedValueOnce({
      date: '2026-11-16',
      total_managers: 1,
      managers: [
        {
          manager_id: 'EMP-00002',
          manager_name: 'Sarah Connor',
          department: 'Engineering',
          team_size: 199,
          present: 175,
          late: 8,
          absent: 6,
          on_leave: 7,
          missing_checkout: 3,
          attendance_rate: 91.8,
          avg_work_formatted: '8h 23m'
        }
      ]
    });

    render(
      <BrowserRouter>
        <QueryClientProvider client={createTestQueryClient()}>
          <CeoDashboardView />
        </QueryClientProvider>
      </BrowserRouter>
    );

    // Verify Title & Top KPI numbers via findBy
    expect(await screen.findByText('Executive Workforce Dashboard')).toBeDefined();
    expect(await screen.findByText('30,000')).toBeDefined(); // Total Employees
    expect(await screen.findByText('25,420')).toBeDefined(); // Present
    expect(await screen.findByText('1,205')).toBeDefined(); // Late Arrivals

    // Verify Manager Performance & Team Health Filter
    expect(await screen.findByText('Manager Performance & Team Operations')).toBeDefined();
    expect(await screen.findByText('Needs Review')).toBeDefined();
    expect(await screen.findByText('Excellent')).toBeDefined();
  });

  it('renders Manager Dashboard with team size, team exceptions, and attendance trends', async () => {
    vi.mocked(managerApi.getTeamSummary).mockResolvedValueOnce({
      date: '2026-11-16',
      team_size: 199,
      present: 175,
      late: 8,
      half_day: 3,
      absent: 6,
      on_leave: 7,
      weekly_off: 0,
      missing_checkout: 0,
      attendance_rate: 91.8,
      avg_work_seconds: 30200,
      avg_work_formatted: '8h 23m'
    });
    vi.mocked(managerApi.getTeamAttendanceTrend).mockResolvedValueOnce([]);
    vi.mocked(managerApi.getTeamLeaves).mockResolvedValueOnce({
      records: [],
      total: 0,
      page: 1,
      page_size: 5,
      total_pages: 0
    });
    vi.mocked(managerApi.getTeamExceptions).mockResolvedValueOnce({
      records: [],
      total: 0,
      page: 1,
      page_size: 5,
      total_pages: 0
    });

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <ManagerDashboardView />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Team Operations Dashboard')).toBeDefined();
    expect(await screen.findByText('199')).toBeDefined(); // Team size
    expect(await screen.findByText('175')).toBeDefined(); // Present
  });

  it('renders Employee Dashboard with Welcome banner, punch widget, and individual summary KPIs', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce({
      name: 'emp1@employee360.local',
      email: 'emp1@employee360.local',
      full_name: 'Elena Rostova',
      roles: ['Employee'],
      employee: {
        name: 'EMP-01362',
        employee_id: 'EMP-01362',
        employee_name: 'Elena Rostova',
        department: 'Engineering',
        designation: 'Senior Developer',
        date_of_joining: '2022-03-15',
        employment_status: 'Active'
      }
    });

    vi.mocked(employeeApi.getSummary).mockResolvedValueOnce({
      employee_id: 'EMP-01362',
      total_days: 365,
      present_count: 215,
      late_count: 12,
      half_day_count: 5,
      absent_count: 8,
      leave_count: 15,
      weekly_off_count: 102,
      holiday_count: 8,
      missing_checkout_count: 2,
      attendance_percentage: 91.5,
      avg_daily_work_seconds: 30600,
      avg_daily_work_formatted: '8h 30m',
      avg_monthly_work_seconds: 673200,
      avg_monthly_work_formatted: '187h 0m',
      avg_first_login: '08:58:00',
      avg_last_logout: '18:32:00'
    });

    vi.mocked(employeeApi.getTrend).mockResolvedValueOnce([]);
    vi.mocked(attendanceApi.getTodayAttendance).mockResolvedValueOnce({
      employee_id: 'EMP-01362',
      date: '2026-11-17',
      current_state: 'Checked Out',
      attendance_status: 'Present',
      first_login: '09:00:00',
      last_logout: '18:00:00',
      total_work_seconds: 32400,
      total_work_formatted: '9h 0m',
      total_sessions: 1,
      is_regularized: false,
      punches: []
    });

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <AuthProvider>
          <EmployeeDashboardView />
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText(/Welcome back, Elena Rostova/i)).toBeDefined();
    expect(await screen.findByText(/Senior Developer • Engineering/i)).toBeDefined();
    expect(await screen.findByText('91.5%')).toBeDefined(); // Attendance percentage
    expect(await screen.findByText('215')).toBeDefined(); // Present days
  });
});
