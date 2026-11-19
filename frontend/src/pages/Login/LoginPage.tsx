import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Lock, Mail, ArrowRight, ShieldCheck, UserCheck, User, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('ceo@employee360.local');
  const [password, setPassword] = useState('Admin123!');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setErrorMsg(typeof err === 'string' ? err : 'Invalid login credentials. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const setDemoUser = (userEmail: string) => {
    setEmail(userEmail);
    setPassword('Admin123!');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-4 sm:p-6">
      <div className="w-full max-w-md">
        {/* Brand Card */}
        <div className="text-center mb-6 sm:mb-8">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-xl shadow-indigo-500/20 mb-3">
            <Building2 className="h-6 w-6" />
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">Employee360</h1>
          <p className="text-xs text-indigo-200/70 mt-1">Enterprise Workforce & Attendance Intelligence</p>
        </div>

        {/* Login Form Card */}
        <div className="rounded-3xl border border-white/10 bg-white/95 p-5 sm:p-8 shadow-2xl backdrop-blur-xl">
          <h2 className="text-base font-bold text-slate-900">Sign in to your account</h2>
          <p className="text-xs text-slate-500 mt-0.5">Use your Frappe session credentials</p>

          {errorMsg && (
            <div className="mt-4 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs font-medium text-rose-700">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700">User Email</label>
              <div className="relative mt-1">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@employee360.local"
                  required
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 py-2.5 pl-10 pr-3.5 text-xs text-slate-900 transition focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700">Password</label>
              <div className="relative mt-1">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 py-2.5 pl-10 pr-10 text-xs text-slate-900 transition focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none transition p-0.5 rounded-lg hover:bg-slate-100"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white shadow-md shadow-indigo-500/20 transition hover:bg-indigo-700 active:scale-98 disabled:opacity-50"
            >
              {isLoading ? 'Authenticating...' : 'Sign In'}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          {/* Quick Demo Switcher */}
          <div className="mt-6 sm:mt-8 border-t border-slate-100 pt-5 sm:pt-6">
            <span className="block text-[10px] sm:text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-center">
              Quick Role Switch (Demo Mode)
            </span>
            <div className="mt-3 grid grid-cols-3 gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => setDemoUser('ceo@employee360.local')}
                className={`flex flex-col items-center justify-center rounded-xl border p-2 text-center transition ${
                  email === 'ceo@employee360.local'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 font-bold'
                    : 'border-slate-200 hover:bg-slate-50 text-slate-600'
                }`}
              >
                <ShieldCheck className="h-4 w-4 mb-1 text-indigo-600" />
                <span className="text-[10px] sm:text-[11px] font-semibold">CEO</span>
                <span className="text-[8px] sm:text-[9px] text-slate-400">Alex M.</span>
              </button>

              <button
                type="button"
                onClick={() => setDemoUser('manager1@employee360.local')}
                className={`flex flex-col items-center justify-center rounded-xl border p-2 text-center transition ${
                  email === 'manager1@employee360.local'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 font-bold'
                    : 'border-slate-200 hover:bg-slate-50 text-slate-600'
                }`}
              >
                <UserCheck className="h-4 w-4 mb-1 text-amber-600" />
                <span className="text-[10px] sm:text-[11px] font-semibold">Manager</span>
                <span className="text-[8px] sm:text-[9px] text-slate-400">Sarah C.</span>
              </button>

              <button
                type="button"
                onClick={() => setDemoUser('emp1@employee360.local')}
                className={`flex flex-col items-center justify-center rounded-xl border p-2 text-center transition ${
                  email === 'emp1@employee360.local'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 font-bold'
                    : 'border-slate-200 hover:bg-slate-50 text-slate-600'
                }`}
              >
                <User className="h-4 w-4 mb-1 text-emerald-600" />
                <span className="text-[10px] sm:text-[11px] font-semibold">Employee</span>
                <span className="text-[8px] sm:text-[9px] text-slate-400">Elena R.</span>
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p className="mt-4 sm:mt-6 text-center text-[11px] sm:text-xs text-indigo-200/50">
          MariaDB 10.11 • Frappe Framework Python Architecture
        </p>
      </div>
    </div>
  );
};
