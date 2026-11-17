import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SearchAutocomplete } from '../components/common/SearchAutocomplete';
import { PunchWidget } from '../components/attendance/PunchWidget';
import { LeaveApplyModal } from '../components/leave/LeaveApplyModal';
import { AttendanceCalendarView } from '../components/attendance/AttendanceCalendarView';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { StatusBadge } from '../components/common/StatusBadge';
import { AuthProvider } from '../hooks/useAuth';

// Mock APIs
vi.mock('../api/client', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn()
  },
  ceoApi: {
    searchEmployees: vi.fn()
  },
  attendanceApi: {
    getTodayAttendance: vi.fn(),
    checkIn: vi.fn(),
    checkOut: vi.fn()
  },
  employeeApi: {
    applyLeave: vi.fn(),
    getActivity: vi.fn()
  }
}));

import { ceoApi, attendanceApi, employeeApi, authApi } from '../api/client';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0
      }
    }
  });

describe('User Interactions & UI State Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('SearchAutocomplete debounces input and renders suggestions', async () => {
    vi.mocked(ceoApi.searchEmployees).mockResolvedValue([
      { name: 'EMP-00012', employee_id: 'EMP-00012', employee_name: 'Sarah Connor', department: 'Engineering', designation: 'VP Engineering' },
      { name: 'EMP-01362', employee_id: 'EMP-01362', employee_name: 'Elena Rostova', department: 'Engineering', designation: 'Senior Developer' }
    ]);

    const onSelect = vi.fn();
    render(<SearchAutocomplete onSelectEmployee={onSelect} />);

    const input = screen.getByPlaceholderText(/search by employee name or id/i);
    fireEvent.change(input, { target: { value: 'Connor' } });

    // Wait for debounced search to trigger and render suggestion
    const suggestion = await screen.findByText('Sarah Connor', {}, { timeout: 2000 });
    expect(suggestion).toBeDefined();

    // Clicking suggestion fires onSelect
    fireEvent.click(suggestion);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ employee_name: 'Sarah Connor', employee_id: 'EMP-00012' })
    );
  });

  it('PunchWidget renders status and initiates check-in with geolocation permission handling', async () => {
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

    vi.mocked(attendanceApi.getTodayAttendance).mockResolvedValueOnce({
      employee_id: 'EMP-01362',
      date: '2026-11-17',
      current_state: 'Checked Out',
      attendance_status: 'Present',
      first_login: null,
      last_logout: null,
      total_work_seconds: 0,
      total_work_formatted: '0h 0m',
      total_sessions: 0,
      is_regularized: false,
      punches: []
    });

    // Mock navigator.geolocation
    const mockGeolocation = {
      getCurrentPosition: vi.fn((success) =>
        success({
          coords: { latitude: 37.7749, longitude: -122.4194, accuracy: 12.0 }
        })
      )
    };
    Object.defineProperty(global.navigator, 'geolocation', {
      value: mockGeolocation,
      writable: true
    });

    vi.mocked(attendanceApi.checkIn).mockResolvedValueOnce({
      message: 'Check-in recorded'
    });

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <AuthProvider>
          <PunchWidget />
        </AuthProvider>
      </QueryClientProvider>
    );

    const punchBtn = await screen.findByRole('button', { name: /clock in/i });
    expect(punchBtn).toBeDefined();
    expect(await screen.findByText(/Live Attendance Status/i)).toBeDefined();

    // Click Check In
    fireEvent.click(punchBtn);

    await waitFor(() => {
      expect(attendanceApi.checkIn).toHaveBeenCalledWith(
        expect.objectContaining({
          latitude: 37.7749,
          longitude: -122.4194,
          gps_accuracy: 12.0
        })
      );
    });
  });

  it('LeaveApplyModal validates required fields and rejects submission without fields', async () => {
    const { container } = render(
      <QueryClientProvider client={createTestQueryClient()}>
        <LeaveApplyModal isOpen={true} onClose={vi.fn()} employeeId="EMP-01362" />
      </QueryClientProvider>
    );

    expect(screen.getByText('Apply for Leave')).toBeDefined();

    const submitBtn = screen.getByRole('button', { name: /apply leave/i });

    // Submit with empty reason
    fireEvent.click(submitBtn);

    // Form prevents empty submission
    expect(employeeApi.applyLeave).not.toHaveBeenCalled();
  });

  it('StatusBadge maps states to proper styling and labels', () => {
    const { rerender } = render(<StatusBadge status="Present" />);
    expect(screen.getByText('Present')).toBeDefined();

    rerender(<StatusBadge status="On Leave" />);
    expect(screen.getByText('On Leave')).toBeDefined();

    rerender(<StatusBadge status="Missing Check-out" />);
    expect(screen.getByText('Missing Check-out')).toBeDefined();
  });

  it('renders LoadingSkeleton, EmptyState, and ErrorState components gracefully', () => {
    // 1. Loading Skeleton
    const { unmount } = render(<LoadingSkeleton rows={4} height="h-10" />);
    unmount();

    // 2. Empty State
    const { rerender } = render(
      <EmptyState title="No records found" message="Please try adjusting your filters." />
    );
    expect(screen.getByText('No records found')).toBeDefined();
    expect(screen.getByText('Please try adjusting your filters.')).toBeDefined();

    // 3. Error State with Retry
    const onRetry = vi.fn();
    rerender(<ErrorState message="Server connection failed" onRetry={onRetry} />);
    expect(screen.getByText('Server connection failed')).toBeDefined();
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders AttendanceCalendarView with month header, weekday columns, and summary metrics', async () => {
    vi.mocked(employeeApi.getActivity).mockResolvedValueOnce({
      records: [
        {
          name: 'LOG-001',
          employee: 'EMP-01362',
          activity_date: '2026-11-16',
          attendance_status: 'Present',
          first_login: 32400,
          last_logout: 64800,
          total_work_seconds: 32400,
          active_seconds: 32400,
          total_sessions: 1,
          calculated_at: '2026-11-16 18:00:00'
        }
      ],
      total: 1,
      page: 1,
      page_size: 50,
      total_pages: 1
    });

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <AttendanceCalendarView employeeId="EMP-01362" />
      </QueryClientProvider>
    );

    expect(await screen.findByText(/November 2026/i)).toBeDefined();
    expect(await screen.findByText('Mon')).toBeDefined();
    expect(await screen.findByText('Fri')).toBeDefined();
    expect(await screen.findByText('1 days')).toBeDefined(); // 1 day present
  });
});
