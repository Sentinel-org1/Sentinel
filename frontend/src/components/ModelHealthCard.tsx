import React from 'react';
import { Link } from 'react-router-dom';
import { Model, DriftEvent, Alert } from '../store';
import Card from './ui/Card';
import Badge from './ui/Badge';

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

  let healthColor = 'text-emerald-450';
  let healthBg = 'bg-emerald-500/10 border-emerald-500/25';
  let healthLabel = 'HEALTHY';

  if (hasCritical) {
    healthColor = 'text-rose-450';
    healthBg = 'bg-rose-500/10 border-rose-500/25';
    healthLabel = 'DRIFT CRITICAL';
  } else if (hasWarning) {
    healthColor = 'text-amber-450';
    healthBg = 'bg-amber-500/10 border-amber-500/25';
    healthLabel = 'DRIFT WARNING';
  }

  // Get latest drift event
  const latestEvent = driftEvents
    .filter((e) => e.model_id === model.id)
    .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime())[0];

  return (
    <Card className="hover:border-blue-500/40 transition-all duration-300">
      <div className="flex flex-col space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <h4 className="text-base font-bold text-slate-100 truncate">{model.name}</h4>
            <p className="text-[10px] text-slate-500 font-semibold mt-0.5">
              VERSION {model.version} • {model.task_type.toUpperCase()}
            </p>
          </div>
          <span className={`px-2 py-0.5 rounded-full border text-[9px] font-bold ${healthBg} ${healthColor} uppercase tracking-wider`}>
            {healthLabel}
          </span>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 bg-slate-950/30 p-3 rounded-lg border border-slate-850">
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
              Last Score
            </span>
            <span className="text-sm font-bold text-slate-200 mt-0.5">
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
          <span className="text-slate-450">
            {modelAlerts.length} open issues pending
          </span>
          <Link
            to={`/models/${model.id}`}
            className="inline-flex items-center text-blue-450 hover:text-blue-300 font-semibold transition-colors"
          >
            Monitor detail
            <svg className="w-3.5 h-3.5 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </Card>
  );
}
