import React from 'react';
import { Link } from 'react-router-dom';
import { Model, DriftEvent, Alert } from '../store';
import Card from './ui/Card';

interface ModelHealthCardProps {
  model: Model;
  driftEvents: DriftEvent[];
  alerts: Alert[];
}

export default function ModelHealthCard({ model, driftEvents, alerts }: ModelHealthCardProps) {
  // Determine overall status
  const modelAlerts = alerts.filter((a) => a.model_id === model.id && a.status === 'open');
  const hasCritical = modelAlerts.some((a) => a.severity === 'critical');
  const hasWarning = modelAlerts.some((a) => a.severity === 'warn');

  let cardBorderClass = 'border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.02)] hover:border-emerald-500/40 hover:shadow-[0_0_25px_rgba(16,185,129,0.12)] hover:scale-[1.015]';
  let accentBarClass = 'bg-gradient-to-b from-emerald-400 to-emerald-500';
  let ambientWashClass = 'bg-emerald-500/[0.03]';

  if (hasCritical) {
    cardBorderClass = 'border-rose-500/20 animate-pulse-crimson hover:scale-[1.015]';
    accentBarClass = 'bg-gradient-to-b from-rose-500 to-rose-600 animate-[pulse_2s_infinite]';
    ambientWashClass = 'bg-rose-500/[0.05]';
  } else if (hasWarning) {
    cardBorderClass = 'border-amber-500/20 shadow-[0_0_15px_rgba(245,158,11,0.02)] hover:border-amber-500/40 hover:shadow-[0_0_25px_rgba(245,158,11,0.12)] hover:scale-[1.015]';
    accentBarClass = 'bg-gradient-to-b from-amber-400 to-amber-500';
    ambientWashClass = 'bg-amber-500/[0.04]';
  }

  // Get latest drift event
  const latestEvent = driftEvents
    .filter((e) => e.model_id === model.id)
    .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime())[0];

  return (
    <Card hoverEffect={false} className={`transition-all duration-300 relative ${cardBorderClass}`}>
      {/* Absolute status left accent bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${accentBarClass}`} />
      
      {/* Absolute status ambient background wash */}
      <div className={`absolute inset-0 pointer-events-none ${ambientWashClass}`} />

      <div className="flex flex-col space-y-4 pl-1">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <h4 className="text-base font-bold text-slate-100 truncate tracking-tight">{model.name}</h4>
            <p className="text-[10px] text-slate-500 font-bold mt-0.5 tracking-wider">
              VERSION <span className="font-mono">{model.version}</span> • {model.task_type.toUpperCase()}
            </p>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 bg-slate-950/40 p-3 rounded-lg border border-slate-850/50">
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
              Last Score
            </span>
            <span className="text-sm font-bold text-slate-200 mt-0.5 font-mono tracking-wide">
              {latestEvent ? latestEvent.score.toFixed(4) : '—'}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
              Detector
            </span>
            <span className="text-xs font-semibold text-slate-350 mt-1 truncate uppercase">
              {latestEvent ? latestEvent.detector.replace('_', ' ') : 'N/A'}
            </span>
          </div>
        </div>

        {/* Summary Info */}
        <div className="flex items-center justify-between text-xs pt-1">
          <span className="text-slate-450 font-medium">
            <span className="font-mono font-bold text-slate-300">{modelAlerts.length}</span> open issues pending
          </span>
          <Link
            to={`/models/${model.id}`}
            className="group inline-flex items-center text-blue-450 hover:text-blue-350 font-bold transition-colors"
          >
            Monitor detail
            <svg className="w-3.5 h-3.5 ml-1 transform transition-transform duration-200 group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </Card>
  );
}
