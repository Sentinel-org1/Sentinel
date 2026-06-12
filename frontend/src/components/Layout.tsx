import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '../store';
import AlertBell from './AlertBell';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useStore((state) => state.user);
  const logout = useStore((state) => state.logout);
  const wsStatus = useStore((state) => state.wsStatus);
  const [isBannerDismissed, setIsBannerDismissed] = useState(false);

  // Re-enable banner if status drops to disconnected again
  useEffect(() => {
    if (wsStatus === 'disconnected') {
      setIsBannerDismissed(false);
    }
  }, [wsStatus]);

  const models = useStore((state) => state.models);
  const [activeFlyout, setActiveFlyout] = useState<string | null>(null);

  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      path: '/',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
        </svg>
      ),
      subItems: [
        { label: 'Overview Metrics', path: '/' },
        { label: 'Platform Summary', path: '/' },
      ]
    },
    {
      id: 'models',
      label: 'Models Registry',
      path: '/models',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
      subItems: [
        { label: 'All Registered Models', path: '/models' },
        ...models.map((m) => ({ label: m.name, path: `/models/${m.id}` })),
      ]
    },
    {
      id: 'alerts',
      label: 'Alerts',
      path: '/alerts',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      ),
      subItems: [
        { label: 'Active Alerts Queue', path: '/alerts' },
      ]
    },
    {
      id: 'calibration',
      label: 'Calibration',
      path: '/calibration',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
        </svg>
      ),
      subItems: [
        { label: 'Threshold Tuner', path: '/calibration' },
      ]
    },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-[#060913] to-[#020306] text-slate-100 flex font-sans antialiased">
      {/* Sidebar Parent Container */}
      <div 
        className="relative flex z-40"
        onMouseLeave={() => setActiveFlyout(null)}
      >
        {/* Narrow 60px Icon Rail */}
        <aside className="w-[60px] bg-slate-900/40 backdrop-blur-xl border-r border-slate-800/50 flex flex-col items-center py-6 shrink-0 relative z-40">
          {/* Brand Logo */}
          <div className="h-10 flex items-center justify-center mb-8">
            <div className="bg-gradient-to-tr from-blue-500 to-indigo-500 p-1.5 rounded-lg mr-0 shadow-md shadow-blue-500/10">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
          </div>

          {/* Icon Buttons Navigation */}
          <nav className="flex-1 flex flex-col items-center space-y-4 w-full px-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || 
                (item.id === 'models' && location.pathname.startsWith('/models/'));
              return (
                <button
                  key={item.id}
                  onMouseEnter={() => setActiveFlyout(item.id)}
                  onClick={() => {
                    navigate(item.path);
                    setActiveFlyout(null);
                  }}
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-250 border outline-none ${
                    isActive
                      ? 'bg-blue-600/15 text-blue-400 border-blue-500/25 shadow-inner'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-transparent'
                  }`}
                  title={item.label}
                >
                  {item.icon}
                </button>
              );
            })}
          </nav>

          {/* User profile footer */}
          <div className="w-10 h-10 rounded-lg bg-slate-800/40 flex items-center justify-center shrink-0 border border-slate-700/60 text-xs font-semibold text-slate-350 hover:bg-slate-700/50 cursor-pointer">
            {user?.email?.charAt(0).toUpperCase() || 'A'}
          </div>
        </aside>

        {/* Contextual Flyout Panel */}
        <div 
          className={`absolute left-[60px] top-0 h-full w-56 bg-[#0a0715]/90 backdrop-blur-2xl border-r border-slate-800/50 flex flex-col py-6 px-4 z-30 transition-all duration-300 transform shadow-2xl ${
            activeFlyout 
              ? 'opacity-100 translate-x-0' 
              : 'opacity-0 -translate-x-4 pointer-events-none'
          }`}
        >
          {/* Header */}
          <div className="h-10 flex items-center border-b border-slate-850 pb-4 mb-4">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              {navItems.find(n => n.id === activeFlyout)?.label || 'Navigation'}
            </span>
          </div>

          {/* Subitems Links */}
          <div className="flex-1 space-y-1 overflow-y-auto pr-1">
            {navItems.find(n => n.id === activeFlyout)?.subItems.map((sub, idx) => {
              const isSubActive = location.pathname === sub.path;
              return (
                <Link
                  key={idx}
                  to={sub.path}
                  onClick={() => setActiveFlyout(null)}
                  className={`block px-3 py-2 rounded-lg text-xs font-medium truncate border transition-all duration-200 ${
                    isSubActive
                      ? 'bg-blue-600/10 text-blue-400 border-blue-500/20'
                      : 'text-slate-300 hover:text-slate-100 hover:bg-slate-800/30 border-transparent'
                  }`}
                >
                  {sub.label}
                </Link>
              );
            })}
          </div>

          {/* Logout Button */}
          <div className="pt-4 border-t border-slate-850">
            <button
              onClick={handleLogout}
              className="w-full flex items-center px-3 py-2 text-xs font-medium text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors border border-transparent outline-none"
            >
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative overflow-hidden">
        {wsStatus === 'disconnected' && (
          <div className="absolute top-0 left-0 right-0 h-48 bg-gradient-to-b from-rose-500/10 via-rose-500/0 to-transparent pointer-events-none z-30 animate-pulse" />
        )}
        
        {/* Top Header */}
        <header className="h-16 border-b border-slate-800 bg-slate-900/40 backdrop-blur-md flex items-center justify-between px-8 z-10 shrink-0">
          <h2 className="text-lg font-semibold text-slate-200 capitalize">
            {location.pathname === '/' ? 'Overview' : location.pathname.substring(1).replace('-', ' ')}
          </h2>
          <div className="flex items-center space-x-4">
            <AlertBell />
          </div>
        </header>

        {/* Dismissible Offline Banner */}
        {wsStatus === 'disconnected' && !isBannerDismissed && (
          <div className="bg-rose-950/40 border-b border-rose-900/50 px-8 py-3 flex items-center justify-between z-20 transition-all duration-300">
            <div className="flex items-center space-x-3 text-rose-400 text-xs font-semibold">
              <svg className="w-4 h-4 animate-bounce shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>System State Broken: Real-time streams are currently OFFLINE. Attempting to reconnect...</span>
            </div>
            <button
              onClick={() => setIsBannerDismissed(true)}
              className="text-rose-400/70 hover:text-rose-350 p-1.5 rounded-lg hover:bg-rose-500/10 transition-colors"
              title="Dismiss banner"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Content Body */}
        <main className="flex-1 overflow-y-auto p-8 bg-transparent relative">
          <div className="absolute top-[10%] right-[5%] w-[40%] h-[40%] bg-indigo-500/5 rounded-full blur-[120px] pointer-events-none" />
          <div className="absolute bottom-[10%] left-[5%] w-[35%] h-[35%] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none" />
          <div className="max-w-7xl mx-auto relative z-10">{children}</div>
        </main>
      </div>
    </div>
  );
}
