import React from 'react';
import { useStore } from '../store';
import client from '../api/client';
import Badge from './ui/Badge';

interface AlertDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AlertDrawer({ isOpen, onClose }: AlertDrawerProps) {
  const alerts = useStore((state) => state.alerts);
  const updateAlertStatus = useStore((state) => state.updateAlertStatus);

  if (!isOpen) return null;

  const openAlerts = alerts.filter((a) => a.status === 'open');

  const handleResolve = async (alertId: number) => {
    try {
      await client.patch(`/api/alerts/${alertId}`, {
        status: 'resolved',
        comment: 'Resolved from Quick Actions drawer',
      });
      updateAlertStatus(alertId, 'resolved');
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div className="fixed right-0 top-0 bottom-0 w-96 bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col font-sans">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div>
            <h3 className="text-base font-bold text-slate-100">Live Alerts Feed</h3>
            <p className="text-[10px] text-slate-450 mt-0.5">{openAlerts.length} active warnings</p>
          </div>
          <button 
            onClick={onClose}
            title="Close Live Alerts Feed"
            className="p-1 text-slate-500 hover:text-slate-300 rounded-lg hover:bg-slate-800 transition-all outline-none"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {openAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-center h-full text-slate-550 space-y-2">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs font-semibold text-slate-350">All systems operational</p>
              <p className="text-[10px] text-slate-500">No unacknowledged drift alerts pending.</p>
            </div>
          ) : (
            openAlerts.map((alert) => (
              <div 
                key={alert.id}
                className="bg-slate-950/40 border border-slate-800/80 rounded-xl p-4 flex flex-col space-y-3 hover:border-slate-700/80 transition-all duration-200"
              >
                <div className="flex items-center justify-between">
                  <Badge variant={alert.severity === 'critical' ? 'critical' : 'warn'} size="sm">
                    {alert.severity}
                  </Badge>
                  <span className="text-[10px] text-slate-500">
                    {new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-200">
                    Model #{alert.model_id} Drift Warning
                  </p>
                  <p className="text-[10px] text-slate-450 mt-1 leading-normal">
                    Drift event ID #{alert.drift_event_id} has exceeded control thresholds. Immediate triage suggested.
                  </p>
                </div>
                <button
                  onClick={() => handleResolve(alert.id)}
                  className="w-full py-1.5 text-[10px] font-bold text-center rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-emerald-450 hover:bg-emerald-500/20 transition-all outline-none"
                >
                  Mark as Resolved
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
