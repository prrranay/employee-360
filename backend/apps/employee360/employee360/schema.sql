-- ==============================================================================
-- Employee360 MariaDB Schema & Performance Index Definitions
-- Supporting 30,000 Employees and 10,950,000 Activity Logs
-- ==============================================================================

-- 1. Shift
CREATE TABLE IF NOT EXISTS `tabShift` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `shift_name` VARCHAR(140) NOT NULL UNIQUE,
  `start_time` TIME NOT NULL,
  `end_time` TIME NOT NULL,
  `grace_period_mins` INT DEFAULT 15,
  `expected_working_hours` DECIMAL(4,2) DEFAULT 8.00,
  `weekly_off_days` VARCHAR(255) DEFAULT 'Saturday, Sunday',
  `applicable_departments` TEXT DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Employee
CREATE TABLE IF NOT EXISTS `tabEmployee` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `employee_id` VARCHAR(50) NOT NULL UNIQUE,
  `employee_name` VARCHAR(140) NOT NULL,
  `user_id` VARCHAR(140) DEFAULT NULL UNIQUE,
  `manager` VARCHAR(140) DEFAULT NULL,
  `department` VARCHAR(100) NOT NULL,
  `designation` VARCHAR(100) NOT NULL,
  `date_of_joining` DATE NOT NULL,
  `employment_status` ENUM('Active', 'Inactive', 'Suspended', 'Left') NOT NULL DEFAULT 'Active',
  `shift` VARCHAR(140) DEFAULT NULL,
  INDEX `idx_emp_id` (`employee_id`),
  INDEX `idx_emp_name` (`employee_name`),
  INDEX `idx_emp_manager` (`manager`),
  INDEX `idx_emp_department` (`department`),
  INDEX `idx_emp_user` (`user_id`),
  CONSTRAINT `fk_employee_shift` FOREIGN KEY (`shift`) REFERENCES `tabShift` (`name`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Employee Checkin (Raw punch events)
CREATE TABLE IF NOT EXISTS `tabEmployee Checkin` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `employee` VARCHAR(140) NOT NULL,
  `time` DATETIME NOT NULL,
  `log_type` ENUM('IN', 'OUT') NOT NULL,
  `source` ENUM('Web', 'Mobile', 'Seed', 'Admin Correction') NOT NULL DEFAULT 'Web',
  `source_record_id` VARCHAR(140) DEFAULT NULL,
  `ip_address` VARCHAR(45) DEFAULT NULL,
  `latitude` DECIMAL(10,8) DEFAULT NULL,
  `longitude` DECIMAL(11,8) DEFAULT NULL,
  `gps_accuracy` DECIMAL(8,2) DEFAULT NULL,
  `device_info` TEXT DEFAULT NULL,
  INDEX `idx_checkin_emp_time` (`employee`, `time`),
  CONSTRAINT `fk_checkin_employee` FOREIGN KEY (`employee`) REFERENCES `tabEmployee` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Employee Activity Log (One derived daily summary per employee per date)
-- 10,950,000 rows target dataset
CREATE TABLE IF NOT EXISTS `tabEmployee Activity Log` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `employee` VARCHAR(140) NOT NULL,
  `activity_date` DATE NOT NULL,
  `attendance_status` ENUM('Present', 'Late', 'Half Day', 'Absent', 'On Leave', 'Weekly Off', 'Holiday', 'Missing Check-out', 'Pending Review') NOT NULL,
  `first_login` TIME DEFAULT NULL,
  `last_logout` TIME DEFAULT NULL,
  `total_work_seconds` INT UNSIGNED NOT NULL DEFAULT 0,
  `active_seconds` INT UNSIGNED NOT NULL DEFAULT 0,
  `total_sessions` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `calculated_at` DATETIME NOT NULL,
  -- Exactly one record per employee per date
  UNIQUE KEY `uk_eal_emp_date` (`employee`, `activity_date`),
  -- Composite indexes for high performance aggregations across 10.95M rows
  INDEX `idx_eal_emp_date` (`employee`, `activity_date`),
  INDEX `idx_eal_date_emp` (`activity_date`, `employee`),
  INDEX `idx_eal_status_date` (`attendance_status`, `activity_date`),
  INDEX `idx_eal_date_status` (`activity_date`, `attendance_status`),
  CONSTRAINT `fk_eal_employee` FOREIGN KEY (`employee`) REFERENCES `tabEmployee` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Leave Application
CREATE TABLE IF NOT EXISTS `tabLeave Application` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `employee` VARCHAR(140) NOT NULL,
  `leave_type` ENUM('Casual Leave', 'Sick Leave', 'Earned Leave', 'Unpaid Leave') NOT NULL,
  `from_date` DATE NOT NULL,
  `to_date` DATE NOT NULL,
  `reason` TEXT NOT NULL,
  `status` ENUM('Pending', 'Approved', 'Rejected', 'Cancelled') NOT NULL DEFAULT 'Pending',
  `approver` VARCHAR(140) DEFAULT NULL,
  `approval_comments` TEXT DEFAULT NULL,
  `applied_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `decision_at` DATETIME DEFAULT NULL,
  INDEX `idx_leave_emp_status_dates` (`employee`, `status`, `from_date`, `to_date`),
  CONSTRAINT `fk_leave_employee` FOREIGN KEY (`employee`) REFERENCES `tabEmployee` (`name`) ON DELETE CASCADE,
  CONSTRAINT `fk_leave_approver` FOREIGN KEY (`approver`) REFERENCES `tabEmployee` (`name`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Attendance Exception
CREATE TABLE IF NOT EXISTS `tabAttendance Exception` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `employee` VARCHAR(140) NOT NULL,
  `activity_date` DATE NOT NULL,
  `exception_type` ENUM('Missing Check-in', 'Missing Check-out', 'Late Arrival', 'Early Departure', 'Unexcused Absence') NOT NULL,
  `description` TEXT DEFAULT NULL,
  `status` ENUM('Open', 'Pending Review', 'Resolved', 'Ignored') NOT NULL DEFAULT 'Open',
  `assigned_manager` VARCHAR(140) DEFAULT NULL,
  `resolution_comments` TEXT DEFAULT NULL,
  `resolved_by` VARCHAR(140) DEFAULT NULL,
  `resolved_at` DATETIME DEFAULT NULL,
  INDEX `idx_exc_mgr_status` (`assigned_manager`, `status`, `activity_date`),
  INDEX `idx_exc_emp_date` (`employee`, `activity_date`),
  CONSTRAINT `fk_exc_employee` FOREIGN KEY (`employee`) REFERENCES `tabEmployee` (`name`) ON DELETE CASCADE,
  CONSTRAINT `fk_exc_manager` FOREIGN KEY (`assigned_manager`) REFERENCES `tabEmployee` (`name`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Seed Checkpoint (Resumability and tracking)
CREATE TABLE IF NOT EXISTS `tabSeed Checkpoint` (
  `seed_key` VARCHAR(64) NOT NULL PRIMARY KEY,
  `last_completed_batch` INT NOT NULL DEFAULT 0,
  `total_records_inserted` BIGINT NOT NULL DEFAULT 0,
  `target_records` BIGINT NOT NULL DEFAULT 10950000,
  `status` ENUM('Pending', 'In Progress', 'Completed', 'Failed') NOT NULL DEFAULT 'Pending',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 8. Core User, Role, and Session Tables
CREATE TABLE IF NOT EXISTS `tabUser` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `email` VARCHAR(140) NOT NULL UNIQUE,
  `first_name` VARCHAR(140) DEFAULT NULL,
  `last_name` VARCHAR(140) DEFAULT NULL,
  `full_name` VARCHAR(140) DEFAULT NULL,
  `username` VARCHAR(140) DEFAULT NULL,
  `password` VARCHAR(255) DEFAULT NULL,
  `enabled` INT(1) NOT NULL DEFAULT 1,
  `user_type` VARCHAR(50) DEFAULT 'System User'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tabHas Role` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `parent` VARCHAR(140) NOT NULL,
  `parenttype` VARCHAR(140) NOT NULL DEFAULT 'User',
  `parentfield` VARCHAR(140) NOT NULL DEFAULT 'roles',
  `role` VARCHAR(140) NOT NULL,
  INDEX `idx_has_role_parent` (`parent`),
  INDEX `idx_has_role_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tabSessions` (
  `user` VARCHAR(140) NOT NULL,
  `sid` VARCHAR(140) NOT NULL PRIMARY KEY,
  `sessiondata` LONGTEXT DEFAULT NULL,
  `ipaddress` VARCHAR(45) DEFAULT NULL,
  `lastupdate` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `status` VARCHAR(20) DEFAULT 'Active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
