import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from '../layouts/AppLayout';
import { Sidebar } from '../layouts/Sidebar';
import { Header } from '../layouts/Header';
import { AuthProvider } from '../hooks/useAuth';

// Mock API client
vi.mock('../api/client', () => ({
  authApi: {
    getCurrentUser: vi.fn(),
    login: vi.fn(),
    logout: vi.fn()
  },
  ceoApi: {
    searchEmployees: vi.fn()
  }
}));

import { authApi } from '../api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false }
  }
});

describe('Mobile Responsive Layout & Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
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
  });

  it('renders Header with mobile hamburger menu toggle button', async () => {
    const onToggle = vi.fn();
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <Header onToggleSidebar={onToggle} />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    const toggleBtn = screen.getByLabelText(/toggle navigation drawer/i);
    expect(toggleBtn).toBeDefined();

    fireEvent.click(toggleBtn);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('Sidebar responds to open and close states on mobile', () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <Sidebar isOpen={false} onClose={onClose} />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    // When closed, sidebar has -translate-x-full
    const aside = screen.getByRole('complementary');
    expect(aside.className).toContain('-translate-x-full');

    // Rerender as open
    rerender(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <Sidebar isOpen={true} onClose={onClose} />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    expect(aside.className).toContain('translate-x-0');

    // Close button works
    const closeBtn = screen.getByLabelText(/close menu/i);
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('AppLayout coordinates mobile sidebar toggling with Header and Sidebar', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <AppLayout />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    );

    const aside = screen.getByRole('complementary');
    expect(aside.className).toContain('-translate-x-full');

    // Click mobile hamburger menu button in Header
    const toggleBtn = screen.getByLabelText(/toggle navigation drawer/i);
    fireEvent.click(toggleBtn);

    // Sidebar should now be open
    expect(aside.className).toContain('translate-x-0');

    // Clicking close button closes it
    const closeBtn = screen.getByLabelText(/close menu/i);
    fireEvent.click(closeBtn);
    expect(aside.className).toContain('-translate-x-full');
  });
});

