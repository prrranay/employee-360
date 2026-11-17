import React, { createContext, useContext } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/client';
import type { UserProfile, UserRole } from '../types';

interface AuthContextType {
  user: UserProfile | null;
  roles: UserRole[];
  isCeo: boolean;
  isManager: boolean;
  isEmployee: boolean;
  isLoading: boolean;
  login: (usr: string, pwd: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();

  const { data: userProfile, isLoading } = useQuery<UserProfile>({
    queryKey: ['currentUser'],
    queryFn: authApi.getCurrentUser,
    retry: false,
    staleTime: 5 * 60 * 1000 // 5 minutes
  });

  const loginMutation = useMutation({
    mutationFn: ({ usr, pwd }: { usr: string; pwd: string }) => authApi.login(usr, pwd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currentUser'] });
    }
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.clear();
    }
  });

  const roles = userProfile?.roles || [];
  const isCeo = roles.includes('CEO') || roles.includes('System Manager') || roles.includes('Administrator');
  const isManager = roles.includes('Manager') || isCeo;
  const isEmployee = roles.includes('Employee') || roles.length > 0;

  const login = async (usr: string, pwd: string) => {
    await loginMutation.mutateAsync({ usr, pwd });
  };

  const logout = async () => {
    await logoutMutation.mutateAsync();
  };

  return (
    <AuthContext.Provider
      value={{
        user: userProfile || null,
        roles,
        isCeo,
        isManager,
        isEmployee,
        isLoading,
        login,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
