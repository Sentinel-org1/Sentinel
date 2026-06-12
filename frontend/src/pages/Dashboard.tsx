import React, { useEffect } from 'react';
import client from '../api/client';
import { useStore } from '../store';
import ModelHealthCard from '../components/ModelHealthCard';
import DriftEventTimeline from '../components/DriftEventTimeline';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import useAlerts from '../hooks/useAlerts';

function getErrorDetail(error: unknown, fallback: string): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail;
  }

  return fallback;
}

export default function Dashboard() {
  const models = useStore((state) => state.models);
  const setModels = useStore((state) => state.setModels);
  const isLoadingModels = useStore((state) => state.isLoadingModels);
  const setModelsLoading = useStore((state) => state.setModelsLoading);
  const modelsError = useStore((state) => state.modelsError);
  const setModelsError = useStore((state) => state.setModelsError);

  const driftEvents = useStore((state) => state.driftEvents);
  const setDriftEvents = useStore((state) => state.setDriftEvents);
  const wsStatus = useStore((state) => state.wsStatus);

  const { alerts, isLoading: isLoadingAlerts } = useAlerts();

  // Load models on mount
  useEffect(() => {
    async function fetchModels() {
      setModelsLoading(true);
      setModelsError(null);
      try {
        const response = await client.get('/api/models/');
        setModels(response.data);
      } catch (err: unknown) {
        console.error('Failed to fetch models:', err);
        setModelsError(getErrorDetail(err, 'Failed to load registered models'));
      } finally {
        setModelsLoading(false);
      }
    }

    fetchModels();
  }, [setModels, setModelsLoading, setModelsError]);

  // Load all drift events to show in the global overview timeline, ensuring latest events for all models are loaded
  useEffect(() => {
    if (models.length === 0) return;

    async function fetchAllDriftEvents() {
      try {
        const response = await client.get('/api/drift/', {
          params: { days: 7, limit: 50 },
        });
        const events = [...response.data.events];

        // Fetch the single latest drift event for each model to ensure they are present
        const latestEventsPromises = models.map((m) =>
          client.get('/api/drift/', {
            params: { model_id: m.id, limit: 1 },
          })
        );
        const latestEventsResponses = await Promise.all(latestEventsPromises);
        
        latestEventsResponses.forEach((res) => {
          if (res.data.events && res.data.events.length > 0) {
            events.push(res.data.events[0]);
          }
        });

        // Deduplicate by ID
        const uniqueEventsMap = new Map();
        events.forEach((e) => uniqueEventsMap.set(e.id, e));

        setDriftEvents(Array.from(uniqueEventsMap.values()));
      } catch (err) {
        console.error('Failed to fetch all drift events:', err);
      }
    }
    fetchAllDriftEvents();
  }, [models, setDriftEvents]);

  if (isLoadingModels || isLoadingAlerts) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner size="lg" />
      </div>
    );
  }

  if (modelsError) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-450 rounded-xl max-w-2xl mx-auto mt-8 font-sans">
        <h4 className="font-bold text-sm">Dashboard Error</h4>
        <p className="text-xs mt-1 leading-relaxed">{modelsError}</p>
      </div>
    );
  }

  // Count active warnings
  const activeAlerts = alerts.filter((a) => a.status === 'open');
  const criticalAlertsCount = activeAlerts.filter((a) => a.severity === 'critical').length;

  const wsDisplayInfo = {
    connected: { label: 'CONNECTED', color: 'text-emerald-450', bg: 'bg-emerald-500/10', border: 'border-emerald-500/25' },
    connecting: { label: 'CONNECTING', color: 'text-amber-450', bg: 'bg-amber-500/10', border: 'border-amber-500/25' },
    disconnected: { label: 'OFFLINE', color: 'text-rose-450', bg: 'bg-rose-500/10', border: 'border-rose-500/25' },
  }[wsStatus];

  return (
    <div className="space-y-8 font-sans">
      {/* Welcome Banner */}
      <div className="flex flex-col space-y-2">
        <h1 className="text-2xl font-black bg-gradient-to-r from-slate-100 via-slate-105 to-slate-300 bg-clip-text text-transparent">
          Platform Summary
        </h1>
        <p className="text-xs text-slate-450">
          Real-time drift detectors, threshold auto-tuners, and alert triage status
        </p>
      </div>

      {/* Grid Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Stat 1 */}
        <Card hoverEffect={false} className="bg-slate-900/40 relative overflow-hidden transition-all duration-300 hover:scale-[1.015] hover:shadow-[0_0_20px_rgba(34,211,238,0.12)] hover:border-cyan-500/25 border-slate-800/60">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Registered Models</p>
              <h3 className="text-2xl font-black text-slate-150 mt-1 font-mono tracking-wide">{models.length}</h3>
            </div>
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-450 border border-blue-500/25">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>
        </Card>

        {/* Stat 2 */}
        <Card hoverEffect={false} className="bg-slate-900/40 relative overflow-hidden transition-all duration-300 hover:scale-[1.015] hover:shadow-[0_0_20px_rgba(251,191,36,0.12)] hover:border-amber-500/25 border-slate-800/60">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Active Alerts</p>
              <h3 className="text-2xl font-black text-amber-450 mt-1 font-mono tracking-wide">{activeAlerts.length}</h3>
            </div>
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-450 border border-amber-500/25">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
        </Card>

        {/* Stat 3 */}
        <Card hoverEffect={false} className="bg-slate-900/40 relative overflow-hidden transition-all duration-300 hover:scale-[1.015] hover:shadow-[0_0_20px_rgba(244,63,94,0.12)] hover:border-rose-500/25 border-slate-800/60">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Critical Failures</p>
              <h3 className="text-2xl font-black text-rose-450 mt-1 font-mono tracking-wide">{criticalAlertsCount}</h3>
            </div>
            <div className="p-2 bg-rose-500/10 rounded-lg text-rose-450 border border-rose-500/25">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </div>
          </div>
        </Card>

        {/* Stat 4 — Live WebSocket Status */}
        <Card hoverEffect={false} className={`bg-slate-900/40 relative overflow-hidden transition-all duration-300 hover:scale-[1.015] border-slate-800/60 ${
          wsStatus === 'connected' 
            ? 'hover:shadow-[0_0_20px_rgba(16,185,129,0.12)] hover:border-emerald-500/25' 
            : 'hover:shadow-[0_0_20px_rgba(244,63,94,0.12)] hover:border-rose-500/25'
        }`}>
          <div className="flex justify-between items-start">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">WebSocket Streams</p>
              <h3 className={`text-2xl font-black mt-1 font-mono tracking-wide ${wsDisplayInfo.color}`}>{wsDisplayInfo.label}</h3>
            </div>
            <div className={`p-2 ${wsDisplayInfo.bg} rounded-lg ${wsDisplayInfo.color} border ${wsDisplayInfo.border}`}>
              {wsStatus === 'disconnected' ? (
                <svg className="w-5 h-5 animate-bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 10h3v4H5z" />
                  <path d="M8 12h3" />
                  <path d="M16 10h3v4h-3z" />
                  <path d="M13 12h3" />
                  <path stroke="#f43f5e" strokeWidth="2.5" d="M11 8l2 8" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071a9 9 0 0112.138 0M2.05 8.05a13.6 13.6 0 0119.9 0" />
                </svg>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Model health cards list */}
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-lg font-bold text-slate-200 tracking-tight">Active Models</h2>
          {models.length === 0 ? (
            <Card hoverEffect={false} className="text-center py-16 text-slate-550 border-dashed">
              No models registered yet.
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {models.map((model) => (
                <ModelHealthCard
                  key={model.id}
                  model={model}
                  driftEvents={driftEvents}
                  alerts={alerts}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: Live events timeline */}
        <div className="space-y-6">
          <h2 className="text-lg font-bold text-slate-200 tracking-tight flex items-center justify-between">
            <span>Recent Activities</span>
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </h2>
          <Card hoverEffect={false} className="p-6 bg-slate-900/30 max-h-[550px] overflow-y-auto">
            <DriftEventTimeline events={driftEvents} />
          </Card>
        </div>
      </div>
    </div>
  );
}
