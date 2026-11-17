import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/Login/LoginPage';
import { DashboardPage } from '../pages/Dashboard/DashboardPage';
import { EmployeesPage } from '../pages/Employees/EmployeesPage';
import { EmployeeDetailsPage } from '../pages/EmployeeDetails/EmployeeDetailsPage';
import { MyAttendancePage } from '../pages/MyAttendance/MyAttendancePage';
import { TeamPage } from '../pages/Team/TeamPage';
import { LeavePage } from '../pages/Leave/LeavePage';
import { AttendanceExceptionsPage } from '../pages/AttendanceExceptions/AttendanceExceptionsPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated routes wrapped in AppLayout */}
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Company-wide employee directory (CEO or Manager) */}
        <Route
          path="/employees"
          element={
            <ProtectedRoute allowedRoles={['CEO']}>
              <EmployeesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/employees/:employeeId" element={<EmployeeDetailsPage />} />
        
        {/* Personal attendance view */}
        <Route path="/my-attendance" element={<MyAttendancePage />} />
        
        {/* Team dashboard view (Manager / CEO) */}
        <Route
          path="/team"
          element={
            <ProtectedRoute allowedRoles={['Manager', 'CEO']}>
              <TeamPage />
            </ProtectedRoute>
          }
        />
        
        {/* Leave application & overview */}
        <Route path="/leave" element={<LeavePage />} />
        
        {/* Attendance exceptions & corrections */}
        <Route path="/attendance-exceptions" element={<AttendanceExceptionsPage />} />
      </Route>

      {/* Catch-all unknown paths */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

