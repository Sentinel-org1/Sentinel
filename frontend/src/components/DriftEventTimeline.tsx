import React from 'react';
import { DriftEvent } from '../store';
import Badge from './ui/Badge';

interface DriftEventTimelineProps {
  events: DriftEvent[];
}

export default function DriftEventTimeline({ events }: DriftEventTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-slate-800 rounded-xl bg-slate-900/20 text-center">
        <svg className="w-8 h-8 text-slate-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="text-xs text-slate-500 font-medium">No recent drift events logged.</span>
      </div>
    );
  }

  // Sort events by detected_at descending
  const sortedEvents = [...events].sort(
    (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
  );

  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {sortedEvents.map((event, idx) => {
          const isLast = idx === sortedEvents.length - 1;
          const severityColors = {
            info: 'bg-blue-500 ring-blue-500/20',
            warn: 'bg-amber-500 ring-amber-500/20',
            critical: 'bg-rose-500 ring-rose-500/20 animate-pulse',
          };
          const dotColor = severityColors[event.severity] || severityColors.info;

          return (
            <li key={event.id || idx}>
              <div className="relative pb-8 font-sans">
                {!isLast && (
                  <span
                    className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-800"
                    aria-hidden="true"
                  />
                )}
                <div className="relative flex space-x-3">
                  <div>
                    <span
                      className={`h-8.5 w-8.5 rounded-full flex items-center justify-center ring-8 ${dotColor}`}
                    >
                      <span className="h-2 w-2 rounded-full bg-slate-950" />
                    </span>
                  </div>
                  <div className="flex-1 min-w-0 pt-1.5 flex justify-between space-x-4">
                    <div className="text-xs text-slate-300">
                      <p className="font-semibold text-slate-200">
                        {event.detector.toUpperCase()} drift detected on{' '}
                        <span className="text-blue-400 font-bold">{event.metric_name || 'predictions'}</span>
                      </p>
                      <div className="flex items-center space-x-2 mt-1.5">
                        <span className="text-[10px] text-slate-500">
                          Score:{' '}
                          <span className="text-slate-350 font-bold">
                            {event.score.toFixed(4)}
                          </span>
                        </span>
                        <span className="text-[10px] text-slate-500">•</span>
                        <span className="text-[10px] text-slate-500">
                          Threshold:{' '}
                          <span className="text-slate-350 font-bold">
                            {event.threshold.toFixed(2)}
                          </span>
                        </span>
                        {event.drift_type && (
                          <>
                            <span className="text-[10px] text-slate-500">•</span>
                            <Badge variant="default" size="sm" className="lowercase !text-[9px]">
                              {event.drift_type}
                            </Badge>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="text-right text-[10px] whitespace-nowrap text-slate-500 pt-0.5">
                      <time dateTime={event.detected_at}>
                        {new Date(event.detected_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </time>
                    </div>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
