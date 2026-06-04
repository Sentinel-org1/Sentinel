import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

interface STLDecompositionProps {
  scoreHistory: number[];
  trend: number[];
  seasonal: number[];
  residual: number[];
}

export default function STLDecomposition({
  scoreHistory,
  trend,
  seasonal,
  residual,
}: STLDecompositionProps) {
  if (!scoreHistory || scoreHistory.length === 0 || !trend || trend.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
        No STL decomposition data available (requires score history window)
      </div>
    );
  }

  // Align length
  const minLength = Math.min(scoreHistory.length, trend.length, seasonal.length, residual.length);

  const data = Array.from({ length: minLength }, (_, idx) => ({
    index: idx + 1,
    original: scoreHistory[scoreHistory.length - minLength + idx],
    trend: trend[trend.length - minLength + idx],
    seasonal: seasonal[seasonal.length - minLength + idx],
    residual: residual[residual.length - minLength + idx],
  }));

  const renderPanel = (title: string, dataKey: string, strokeColor: string, _fillGrad: string) => {
    interface CustomTooltipProps {
      active?: boolean;
      payload?: Array<{
        value?: number;
      }>;
    }

    return (
      <div className="flex flex-col space-y-1">
        <div className="flex items-center justify-between px-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</span>
        </div>
        <div className="w-full h-32 bg-slate-900/30 border border-slate-800/80 rounded-xl p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.4} />
              <XAxis dataKey="index" stroke="#475569" fontSize={9} tickLine={false} axisLine={false} />
              <YAxis stroke="#475569" fontSize={9} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
              <Tooltip
                content={({ active, payload }: CustomTooltipProps) => {
                  if (active && payload && payload.length) {
                    const colors: Record<string, string> = {
                      '#3b82f6': 'text-blue-400',
                      '#8b5cf6': 'text-purple-400',
                      '#10b981': 'text-emerald-450',
                      '#f43f5e': 'text-rose-400',
                    };
                    const colorClass = colors[strokeColor] || 'text-slate-205';
                    return (
                      <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700 px-2 py-1.5 rounded-md shadow-lg text-[10px]">
                        <p className={`font-semibold ${colorClass}`}>
                          {title}: {payload[0].value !== undefined ? payload[0].value.toFixed(5) : 'N/A'}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke={strokeColor}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col space-y-4">
      {renderPanel('Original Signal (Drift Score)', 'original', '#3b82f6', 'blue')}
      {renderPanel('Trend Component (Underlying Change)', 'trend', '#8b5cf6', 'purple')}
      {renderPanel('Seasonal Component (Periodic Noise)', 'seasonal', '#10b981', 'green')}
      {renderPanel('Residual Component (Unexplained/Noise)', 'residual', '#f43f5e', 'red')}
    </div>
  );
}
