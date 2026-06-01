import React, { useState } from 'react';
import { useStore } from '../store';
import AlertDrawer from './AlertDrawer';

export default function AlertBell() {
  const unreadAlertCount = useStore((state) => state.unreadAlertCount);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsDrawerOpen(true)}
        className="relative p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 rounded-lg transition-all outline-none"
        title="Open Alerts Feed"
      >
        <svg className="w-5.5 h-5.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        {unreadAlertCount > 0 && (
          <span className="absolute top-1 right-1 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-4 w-4 bg-rose-500 text-[9px] font-bold text-white items-center justify-center">
              {unreadAlertCount}
            </span>
          </span>
        )}
      </button>

      <AlertDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} />
    </>
  );
}
