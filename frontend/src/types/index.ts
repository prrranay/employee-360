export type UserRole = 'CEO' | 'Manager' | 'Employee' | 'System Manager' | 'Administrator';

export type AttendanceStatus = 
  | 'Present'
  | 'Late'
  | 'Half Day'
  | 'Absent'
  | 'On Leave'
  | 'Weekly Off'
  | 'Holiday'
  | 'Missing Check-out'
  | 'Pending Review';

export interface Employee {
  name: string;
  employee_id: string;
  employee_name: string;
  department: string;
  designation: string;
  manager?: string | null;
  manager_name?: string | null;
  user_id?: string | null;
  date_of_joining: string;
  employment_status: 'Active' | 'Inactive' | 'Suspended' | 'Left';
  shift?: string;
  shift_details?: {
    shift_name: string;
    start_time: string;
    end_time: string;
    grace_period_mins: number;
    expected_working_hours: number;
    weekly_off_days: string;
  };
}

export interface UserProfile {
  user_id: string;
  roles: UserRole[];
  employee: Employee | null;
}

export interface ActivityLogRecord {
  name: string;
  employee: string;
  activity_date: string;
  attendance_status: AttendanceStatus;
  first_login: string | null;
  last_logout: string | null;
  total_work_seconds: number;
  active_seconds?: number | null;
  total_sessions: number;
  calculated_at: string;
}

export interface PunchRecord {
  name: string;
  time: string;
  log_type: 'IN' | 'OUT';
  source: string;
}

export interface TodayAttendance {
  employee_id: string;
  date: string;
  current_state: 'Checked In' | 'Checked Out';
  attendance_status: AttendanceStatus;
  first_login: string | null;
  last_logout: string | null;
  total_work_seconds: number;
  total_work_formatted: string;
  total_sessions: number;
  is_regularized?: boolean;
  punches: PunchRecord[];
}

export interface EmployeeSummary {
  employee_id: string;
  total_days: number;
  present_count: number;
  late_count: number;
  half_day_count: number;
  absent_count: number;
  leave_count: number;
  weekly_off_count: number;
  holiday_count: number;
  missing_checkout_count: number;
  attendance_percentage: number;
  avg_daily_work_seconds: number;
  avg_daily_work_formatted: string;
  avg_first_login: string | null;
  avg_last_logout: string | null;
}

export interface CompanyDashboardSummary {
  date: string;
  total_employees: number;
  present: number;
  late: number;
  half_day: number;
  absent: number;
  on_leave: number;
  weekly_off: number;
  missing_checkout: number;
  attendance_rate: number;
  avg_work_seconds: number;
  avg_work_formatted: string;
}

export interface TeamDashboardSummary {
  date: string;
  team_size: number;
  present: number;
  late: number;
  half_day: number;
  absent: number;
  on_leave: number;
  weekly_off: number;
  missing_checkout: number;
  attendance_rate: number;
  avg_work_seconds: number;
  avg_work_formatted: string;
}

export interface DepartmentAnalytics {
  department: string;
  total_headcount: number;
  present_count: number;
  late_count: number;
  half_day_count: number;
  absent_count: number;
  leave_count: number;
  missing_checkout_count: number;
  attendance_rate: number;
  avg_work_formatted: string;
}

export interface AttendanceTrendPoint {
  activity_date: string;
  present: number;
  late: number;
  half_day: number;
  absent: number;
  on_leave: number;
  weekly_off: number;
  missing_checkout: number;
}

export interface LeaveApplication {
  name: string;
  employee: string;
  employee_name?: string;
  department?: string;
  leave_type: 'Casual Leave' | 'Sick Leave' | 'Earned Leave' | 'Unpaid Leave';
  from_date: string;
  to_date: string;
  reason: string;
  status: 'Pending' | 'Approved' | 'Rejected' | 'Cancelled';
  applied_at: string;
  decision_at?: string | null;
  approver?: string | null;
  approval_comments?: string | null;
}

export interface LeaveBalance {
  leave_type: 'Casual Leave' | 'Sick Leave' | 'Earned Leave' | 'Unpaid Leave';
  allocated: number;
  used: number;
  pending: number;
  remaining: number;
}

export interface TeamLeaveCalendarEvent {
  name: string;
  employee: string;
  employee_name: string;
  department: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  status: string;
  reason: string;
}

export interface AttendanceException {
  name: string;
  employee: string;
  employee_name?: string;
  department?: string;
  activity_date: string;
  exception_type: 'Missing Check-in' | 'Missing Check-out' | 'Late Arrival' | 'Early Departure' | 'Unexcused Absence';
  description: string;
  status: 'Open' | 'Pending Review' | 'Resolved' | 'Ignored';
  assigned_manager?: string | null;
  manager_name?: string | null;
}

export interface PaginatedResponse<T> {
  records: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ManagerPerformanceItem {
  manager_id: string;
  manager_name: string;
  department: string;
  designation: string;
  team_size: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  on_leave_count: number;
  attendance_rate: number;
  avg_work_seconds: number;
  avg_work_formatted: string;
  performance_status: 'Excellent' | 'Good' | 'Needs Review';
}

export interface ManagerPerformanceResponse {
  date: string;
  managers: ManagerPerformanceItem[];
}

export interface PendingManagerRequestsResponse {
  leaves: Array<{
    name: string;
    employee: string;
    employee_name: string;
    department: string;
    designation: string;
    leave_type: string;
    from_date: string;
    to_date: string;
    reason: string;
    status: string;
    applied_at: string;
  }>;
  corrections: Array<{
    name: string;
    employee: string;
    employee_name: string;
    department: string;
    designation: string;
    activity_date: string;
    exception_type: string;
    description: string;
    status: string;
    assigned_manager: string;
  }>;
  total_pending: number;
}

