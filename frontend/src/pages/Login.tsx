import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';
import { useStore } from '../store';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const setAuth = useStore((state) => state.setAuth);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const response = await client.post('/auth/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token } = response.data;

      // Fetch user detail
      const userResponse = await client.get('/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      setAuth(access_token, userResponse.data);
      navigate('/');
    } catch (err: any) {
      console.error('Login failed:', err);
      setError(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 relative overflow-hidden font-sans">
      {/* Background decoration */}
      <div className="absolute top-[-20%] left-[-20%] w-[60%] h-[60%] bg-blue-600/10 rounded-full blur-[120px]" />
      <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] bg-indigo-600/10 rounded-full blur-[120px]" />

      <div className="w-full max-w-md px-4 z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-gradient-to-tr from-blue-500 to-indigo-500 p-2.5 rounded-xl shadow-lg shadow-blue-500/20 mb-3">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
            SENTINEL
          </h1>
          <p className="text-xs text-slate-450 mt-1">ML Model Observability Platform</p>
        </div>

        <Card 
          title="Welcome Back" 
          subtitle="Sign in to monitor model drift and performance metrics"
          hoverEffect={false}
          className="shadow-2xl border-slate-800/80 bg-slate-900/40"
        >
          <form onSubmit={handleLogin} className="space-y-4">
            {error && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-lg font-medium">
                {error}
              </div>
            )}
            
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-400">Email Address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@sentinel.ai"
                className="w-full bg-slate-950/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-400">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-600 outline-none transition-all"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={loading}
            >
              Sign In
            </Button>
          </form>
        </Card>

        <p className="text-center text-[10px] text-slate-600 mt-6">
          Protected by Sentinel Security and JWT Orchestration.
        </p>
      </div>
    </div>
  );
}
