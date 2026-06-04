import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

interface PSIPoint {
  timestamp: string;
  score: number;
  ewma_mean?: number;
  ewma_threshold?: number;
}

interface PSITimeSeriesProps {
  data: PSIPoint[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
  }>;
  label?: string;
}

export default function PSITimeSeries({ data }: PSITimeSeriesProps) {
  // Format timestamps to reader-friendly dates
  const formattedData = data.map((d) => ({
    ...d,
    displayTime: new Date(d.timestamp).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
  }));

  const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700 p-3 rounded-lg shadow-xl text-xs space-y-1">
          <p className="text-slate-400 font-medium">{label}</p>
          {payload.map((p, idx: number) => {
            const colors: Record<string, string> = {
              'PSI Score': 'text-blue-400',
              'Adaptive Threshold (EWMA)': 'text-amber-400',
              'EWMA Mean': 'text-emerald-400',
            };
            const colorClass = colors[p.name] || 'text-slate-205';
            return (
              <p key={idx} className={`${colorClass} font-semibold`}>
                {p.name}: {p.value !== undefined ? p.value.toFixed(4) : 'N/A'}
              </p>
            );
          })}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-80 bg-slate-900/35 border border-slate-800/80 rounded-xl p-4 shadow-inner">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={formattedData}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="colorThresh" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
          <XAxis
            dataKey="displayTime"
            stroke="#64748b"
            fontSize={10}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            stroke="#64748b"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            domain={[0, (dataMax: number) => Math.max(dataMax * 1.1, 0.3)]}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="top"
            height={36}
            iconType="circle"
            wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }}
          />
          {/* EWMA Band Fill */}
          <Area
            name="Adaptive Threshold (EWMA)"
            type="monotone"
            dataKey="ewma_threshold"
            stroke="#f59e0b"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            fillOpacity={1}
            fill="url(#colorThresh)"
          />
          {/* PSI Score */}
          <Area
            name="PSI Score"
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#colorScore)"
          />
          {/* EWMA Mean */}
          <Line
            name="EWMA Mean"
            type="monotone"
            dataKey="ewma_mean"
            stroke="#10b981"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
