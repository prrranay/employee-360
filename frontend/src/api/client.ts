import axios from 'axios';
import type {
  ActivityLogRecord,
  AttendanceException,
  AttendanceTrendPoint,
  CompanyDashboardSummary,
  DepartmentAnalytics,
  Employee,
  EmployeeSummary,
  LeaveApplication,
  LeaveBalance,
  TeamLeaveCalendarEvent,
  PaginatedResponse,
  TeamDashboardSummary,
  TodayAttendance,
  UserProfile
} from '../types';

export const apiClient = axios.create({
  baseURL: '/api/method',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

// Request interceptor to attach CSRF token for state-mutating requests
apiClient.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrf_token');
  if (csrfToken && ['post', 'put', 'delete', 'patch'].includes((config.method || '').toLowerCase())) {
    config.headers['X-Frappe-CSRF-Token'] = csrfToken;
  }
  return config;
});

// Response interceptor for Frappe `{ message: ... }` unwrapping and 401 handling
apiClient.interceptors.response.use(
  (response) => {
    // Frappe wraps returned values inside `message`
    if (response.data && response.data.message !== undefined) {
      return response.data.message;
    }
    return response.data;
  },
  (error) => {
    if (error.response?.status === 401) {
      // If unauthorized and not already on /login, redirect
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ==========================================
// AUTH APIs
// ==========================================
export const authApi = {
  login: async (usr: string, pwd: string): Promise<{ home_page?: string; full_name?: string }> => {
    return apiClient.post('/login', { usr, pwd });
  },
  logout: async (): Promise<void> => {
    return apiClient.post('/logout');
  },
  getCurrentUser: async (): Promise<UserProfile> => {
    return apiClient.get('/employee360.api.auth_utils.get_session_user_and_roles');
  }
};

// ==========================================
// CEO APIs
// ==========================================
export const ceoApi = {
  getCompanySummary: async (target_date?: string): Promise<CompanyDashboardSummary> => {
    return apiClient.get('/employee360.api.ceo.get_company_dashboard_summary', {
      params: { target_date }
    });
  },
  searchEmployees: async (query: string, limit: number = 10): Promise<Employee[]> => {
    return apiClient.get('/employee360.api.ceo.search_employees', {
      params: { query, limit }
    });
  },
  getEmployeeOverview: async (
    department?: string,
    status?: string,
    shift?: string,
    page: number = 1,
    page_size: number = 25,
    search?: string
  ): Promise<PaginatedResponse<Employee>> => {
    return apiClient.get('/employee360.api.ceo.get_employee_overview', {
      params: { department, status, shift, page, page_size, search }
    });
  },
  getDepartmentAnalytics: async (target_date?: string): Promise<DepartmentAnalytics[]> => {
    return apiClient.get('/employee360.api.ceo.get_department_analytics', {
      params: { target_date }
    });
  },
  getCompanyAttendanceTrend: async (from_date?: string, to_date?: string, days: number = 14): Promise<AttendanceTrendPoint[]> => {
    return apiClient.get('/employee360.api.ceo.get_company_attendance_trend', {
      params: { from_date, to_date, days }
    });
  },
  getCompanyAttendanceExceptions: async (
    target_date?: string,
    exception_type?: string,
    page: number = 1,
    page_size: number = 25
  ): Promise<PaginatedResponse<AttendanceException>> => {
    return apiClient.get('/employee360.api.ceo.get_company_attendance_exceptions', {
      params: { target_date, exception_type, page, page_size }
    });
  },
  getCompanyLeaveOverview: async (
    status?: string,
    department?: string,
    page: number = 1,
    page_size: number = 25
  ): Promise<PaginatedResponse<LeaveApplication>> => {
    return apiClient.get('/employee360.api.ceo.get_company_leave_overview', {
      params: { status, department, page, page_size }
    });
  },
  getManagerPerformance: async (target_date?: string): Promise<{ date: string; managers: any[] }> => {
    return apiClient.get('/employee360.api.ceo.get_manager_performance', {
      params: { target_date }
    });
  },
  getPendingManagerRequests: async (): Promise<{ leaves: any[]; corrections: any[]; total_pending: number }> => {
    return apiClient.get('/employee360.api.ceo.get_pending_manager_requests');
  }
};

// ==========================================
// MANAGER APIs
// ==========================================
export const managerApi = {
  getTeamSummary: async (target_date?: string, include_indirect: number = 1, manager_id?: string): Promise<TeamDashboardSummary> => {
    return apiClient.get('/employee360.api.manager.get_team_dashboard_summary', {
      params: { target_date, include_indirect, manager_id }
    });
  },
  getManagerTeam: async (include_indirect: number = 1, manager_id?: string): Promise<Employee[]> => {
    return apiClient.get('/employee360.api.manager.get_manager_team', {
      params: { include_indirect, manager_id }
    });
  },
  getTeamAttendanceTrend: async (from_date?: string, to_date?: string, days: number = 14, include_indirect: number = 1): Promise<AttendanceTrendPoint[]> => {
    return apiClient.get('/employee360.api.manager.get_team_attendance_trend', {
      params: { from_date, to_date, days, include_indirect }
    });
  },
  getTeamExceptions: async (
    target_date?: string,
    status?: string,
    page: number = 1,
    page_size: number = 25,
    include_indirect: number = 1
  ): Promise<PaginatedResponse<AttendanceException>> => {
    return apiClient.get('/employee360.api.manager.get_team_attendance_exceptions', {
      params: { target_date, status, page, page_size, include_indirect }
    });
  },
  getTeamLeaves: async (status?: string, page: number = 1, page_size: number = 25): Promise<PaginatedResponse<LeaveApplication>> => {
    return apiClient.get('/employee360.api.manager.get_team_leave_overview', {
      params: { status, page, page_size }
    });
  },
  approveLeave: async (leave_id: string, comments?: string): Promise<any> => {
    return apiClient.post('/employee360.api.manager.approve_leave_application', {
      leave_id,
      comments
    });
  },
  rejectLeave: async (leave_id: string, comments?: string): Promise<any> => {
    return apiClient.post('/employee360.api.manager.reject_leave_application', {
      leave_id,
      comments
    });
  },
  getTeamLeaveCalendar: async (from_date?: string, to_date?: string, include_indirect: number = 1): Promise<TeamLeaveCalendarEvent[]> => {
    return apiClient.get('/employee360.api.manager.get_team_leave_calendar', {
      params: { from_date, to_date, include_indirect }
    });
  }
};

// ==========================================
// EMPLOYEE APIs
// ==========================================
export const employeeApi = {
  getProfile: async (employee_id: string): Promise<Employee> => {
    return apiClient.get('/employee360.api.employee.get_employee_profile', {
      params: { employee_id }
    });
  },
  getActivity: async (
    employee_id: string,
    from_date?: string,
    to_date?: string,
    attendance_status?: string,
    page: number = 1,
    page_size: number = 30
  ): Promise<PaginatedResponse<ActivityLogRecord>> => {
    return apiClient.get('/employee360.api.employee.get_employee_activity', {
      params: { employee_id, from_date, to_date, attendance_status, page, page_size }
    });
  },
  getSummary: async (employee_id: string, from_date?: string, to_date?: string): Promise<EmployeeSummary> => {
    return apiClient.get('/employee360.api.employee.get_employee_attendance_summary', {
      params: { employee_id, from_date, to_date }
    });
  },
  getTrend: async (employee_id: string, days: number = 14): Promise<ActivityLogRecord[]> => {
    return apiClient.get('/employee360.api.employee.get_employee_attendance_trend', {
      params: { employee_id, days }
    });
  },
  getLeaveHistory: async (employee_id: string, page: number = 1, page_size: number = 20): Promise<PaginatedResponse<LeaveApplication>> => {
    return apiClient.get('/employee360.api.employee.get_employee_leave_history', {
      params: { employee_id, page, page_size }
    });
  },
  getLeaveBalance: async (employee_id?: string): Promise<LeaveBalance[]> => {
    return apiClient.get('/employee360.api.employee.get_employee_leave_balance', {
      params: { employee_id }
    });
  },
  applyLeave: async (data: {
    leave_type: string;
    from_date: string;
    to_date: string;
    reason: string;
    employee_id?: string;
  }): Promise<any> => {
    return apiClient.post('/employee360.api.employee.apply_leave_application', data);
  },
  cancelLeave: async (leave_id: string): Promise<any> => {
    return apiClient.post('/employee360.api.employee.cancel_leave_application', { leave_id });
  }
};

// ==========================================
// LIVE ATTENDANCE APIs
// ==========================================
export const attendanceApi = {
  checkIn: async (data?: string | { latitude?: number; longitude?: number; device_info?: string }) => {
    const payload = typeof data === 'string' ? { device_info: data } : (data || {});
    return apiClient.post('/employee360.api.attendance.check_in', payload);
  },
  checkOut: async (data?: string | { latitude?: number; longitude?: number; device_info?: string }) => {
    const payload = typeof data === 'string' ? { device_info: data } : (data || {});
    return apiClient.post('/employee360.api.attendance.check_out', payload);
  },
  getTodayAttendance: async (): Promise<TodayAttendance> => {
    return apiClient.get('/employee360.api.attendance.get_today_attendance');
  },
  requestCorrection: async (
    activity_date_or_data: string | { activity_date: string; exception_type?: string; requested_status?: string; requested_in_time?: string; requested_out_time?: string; reason: string },
    requested_status?: string,
    reason?: string
  ) => {
    let payload;
    if (typeof activity_date_or_data === 'string') {
      payload = {
        activity_date: activity_date_or_data,
        requested_status: requested_status || 'Present',
        reason: reason || ''
      };
    } else {
      payload = activity_date_or_data;
    }
    return apiClient.post('/employee360.api.attendance.request_attendance_correction', payload);
  },
  approveException: async (exception_id: string, comments?: string) => {
    return apiClient.post('/employee360.api.attendance.approve_attendance_exception', {
      exception_id,
      comments
    });
  },
  rejectException: async (exception_id: string, comments?: string) => {
    return apiClient.post('/employee360.api.attendance.reject_attendance_exception', {
      exception_id,
      comments
    });
  }
};
