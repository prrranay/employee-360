import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../hooks/useAuth';
import { ProtectedRoute } from '../routes/ProtectedRoute';

// Mock API client
vi.mock('../api/client', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn()
  }
}));

import { authApi } from '../api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false }
  }
});

const DummyDashboard = () => {
  const { user, isCeo, isManager, isEmployee } = useAuth();
  return (
    <div>
      <h1>Dashboard View</h1>
      <p data-testid="user-name">{user?.full_name}</p>
      <p data-testid="is-ceo">{isCeo ? 'YES' : 'NO'}</p>
      <p data-testid="is-mgr">{isManager ? 'YES' : 'NO'}</p>
      <p data-testid="is-emp">{isEmployee ? 'YES' : 'NO'}</p>
    </div>
  );
};

const DummyLogin = () => <h1>Login Page</h1>;
const DummyTeam = () => <h1>Team Page</h1>;

describe('Authentication & Protected Routes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
  });

  it('renders login page when user is not authenticated', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce(null as any);

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/dashboard']}>
            <Routes>
              <Route path="/login" element={<DummyLogin />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DummyDashboard />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText('Login Page')).toBeDefined();
  });

  it('renders dashboard with CEO role and permissions', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce({
      name: 'ceo@employee360.local',
      email: 'ceo@employee360.local',
      full_name: 'Alex Mercer',
      roles: ['CEO'],
      employee: {
        name: 'EMP-00001',
        employee_id: 'EMP-00001',
        employee_name: 'Alex Mercer',
        department: 'Executive',
        designation: 'CEO',
        date_of_joining: '2020-01-01',
        employment_status: 'Active'
      }
    });

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/dashboard']}>
            <Routes>
              <Route path="/login" element={<DummyLogin />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DummyDashboard />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText('Dashboard View')).toBeDefined();
    expect(screen.getByTestId('user-name').textContent).toBe('Alex Mercer');
    expect(screen.getByTestId('is-ceo').textContent).toBe('YES');
    expect(screen.getByTestId('is-mgr').textContent).toBe('YES');
  });

  it('enforces role protection: employee cannot access Manager-only route', async () => {
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

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/team']}>
            <Routes>
              <Route path="/dashboard" element={<DummyDashboard />} />
              <Route
                path="/team"
                element={
                  <ProtectedRoute allowedRoles={['Manager', 'CEO']}>
                    <DummyTeam />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    // Should redirect from /team to /dashboard because Elena is an Employee, not Manager
    expect(await screen.findByText('Dashboard View')).toBeDefined();
    expect(screen.getByTestId('user-name').textContent).toBe('Elena Rostova');
    expect(screen.getByTestId('is-mgr').textContent).toBe('NO');
  });
});

