import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';

interface ShapBarProps {
  topMovers: [string, number][]; // Array of [feature_name, delta_value]
}

export default function ShapBar({ topMovers }: ShapBarProps) {
  if (!topMovers || topMovers.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
        No SHAP attribution data available
      </div>
    );
  }

  const data = topMovers.map(([feature, val]) => ({
    name: feature,
    value: val,
  }));

  interface CustomTooltipProps {
    active?: boolean;
    payload?: Array<{
      value: number;
      payload: {
        name: string;
      };
    }>;
  }

  const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
    if (active && payload && payload.length) {
      const val = payload[0].value;
      const isPositive = val >= 0;
      return (
        <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700 p-2.5 rounded-lg shadow-xl text-xs space-y-1">
          <p className="font-semibold text-slate-200">{payload[0].payload.name}</p>
          <p className={isPositive ? 'text-blue-400 font-semibold' : 'text-rose-400 font-semibold'}>
            Change: {isPositive ? '+' : ''}{val.toFixed(6)}
          </p>
          <p className="text-[10px] text-slate-500 leading-tight max-w-[200px]">
            {isPositive 
              ? 'Feature became more important in driving model predictions compared to baseline.' 
              : 'Feature became less important in driving model predictions compared to baseline.'}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-80 bg-slate-900/35 border border-slate-800/80 rounded-xl p-4 shadow-inner">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} horizontal={false} />
          <XAxis 
            type="number" 
            stroke="#64748b" 
            fontSize={10} 
            tickLine={false} 
            axisLine={false} 
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke="#94a3b8"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            width={100}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.15 }} />
          <ReferenceLine x={0} stroke="#475569" strokeWidth={1} />
          <Bar dataKey="value">
            {data.map((entry, index) => {
              const isPositive = entry.value >= 0;
              return (
                <Cell
                  key={`cell-${index}`}
                  fill={isPositive ? 'url(#blueGrad)' : 'url(#roseGrad)'}
                />
              );
            })}
          </Bar>
          <defs>
            <linearGradient id="blueGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1e3a8a" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.85} />
            </linearGradient>
            <linearGradient id="roseGrad" x1="1" y1="0" x2="0" y2="0">
              <stop offset="0%" stopColor="#9f1239" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity={0.85} />
            </linearGradient>
          </defs>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
