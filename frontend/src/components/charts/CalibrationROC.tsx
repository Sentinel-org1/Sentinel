import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';

interface CalibrationPoint {
  threshold: number;
  tp_rate: number; // TPR (Y-axis)
  fp_rate: number; // FPR (X-axis)
  youden_j: number;
}

interface CalibrationROCProps {
  points: CalibrationPoint[];
  optimalThreshold: number | null;
  auc: number | null;
}

export default function CalibrationROC({
  points,
  optimalThreshold,
  auc,
}: CalibrationROCProps) {
  if (!points || points.length === 0) {
    return (
      <div className="flex items-center justify-center h-56 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
        No calibration data points available. Run calibration to generate.
      </div>
    );
  }

  // Sort by fp_rate then tp_rate to make a clean curve
  const sortedPoints = [...points].sort((a, b) => {
    if (a.fp_rate !== b.fp_rate) return a.fp_rate - b.fp_rate;
    return a.tp_rate - b.tp_rate;
  });

  // Find the point corresponding to optimal threshold
  const optimalPoint = optimalThreshold !== null 
    ? sortedPoints.find(p => Math.abs(p.threshold - optimalThreshold) < 1e-6) || 
      sortedPoints.reduce((prev, curr) => 
        Math.abs(curr.threshold - optimalThreshold) < Math.abs(prev.threshold - optimalThreshold) ? curr : prev
      )
    : null;

  interface ScatterDataPoint {
    x: number;
    y: number;
    threshold: number;
    youden_j: number;
  }

  const scatterData: ScatterDataPoint[] = optimalPoint ? [{
    x: optimalPoint.fp_rate,
    y: optimalPoint.tp_rate,
    threshold: optimalPoint.threshold,
    youden_j: optimalPoint.youden_j,
  }] : [];

  interface TooltipPayload {
    payload?: CalibrationPoint | ScatterDataPoint;
    value?: number;
  }

  interface CustomTooltipProps {
    active?: boolean;
    payload?: TooltipPayload[];
  }

  const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700 p-2.5 rounded-lg shadow-xl text-xs space-y-1">
          <p className="font-semibold text-slate-350">Point Stats</p>
          <p className="text-slate-300">Threshold: <span className="font-semibold">{data && 'threshold' in data ? (data.threshold as number).toFixed(4) : (payload[0].value !== undefined ? payload[0].value.toFixed(4) : '')}</span></p>
          <p className="text-blue-400">TPR (Sensitivity): {data && ('tp_rate' in data ? (data.tp_rate as number).toFixed(3) : 'y' in data ? (data.y as number).toFixed(3) : '')}</p>
          <p className="text-amber-400">FPR (1 - Specificity): {data && ('fp_rate' in data ? (data.fp_rate as number).toFixed(3) : 'x' in data ? (data.x as number).toFixed(3) : '')}</p>
          {data && 'youden_j' in data && (
            <p className="text-emerald-400">Youden's J: {(data.youden_j as number).toFixed(3)}</p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex justify-between items-center text-xs px-2">
        <span className="text-slate-400">
          Area Under Curve (AUC):{' '}
          <span className="text-slate-100 font-bold bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
            {auc !== null ? auc.toFixed(4) : 'N/A'}
          </span>
        </span>
        {optimalThreshold !== null && (
          <span className="text-slate-400">
            Optimal Threshold:{' '}
            <span className="text-slate-100 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              {optimalThreshold.toFixed(4)}
            </span>
          </span>
        )}
      </div>

      <div className="w-full h-80 bg-slate-900/35 border border-slate-800/80 rounded-xl p-4 shadow-inner">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={sortedPoints}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.5} />
            <XAxis
              type="number"
              dataKey="fp_rate"
              name="FPR"
              domain={[0, 1]}
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              label={{ value: 'False Positive Rate (FPR)', position: 'insideBottom', offset: -5, fill: '#64748b', fontSize: 10 }}
            />
            <YAxis
              type="number"
              dataKey="tp_rate"
              name="TPR"
              domain={[0, 1]}
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              label={{ value: 'True Positive Rate (TPR)', angle: -90, position: 'insideLeft', offset: 10, fill: '#64748b', fontSize: 10 }}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Random guess baseline */}
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ]}
              stroke="#475569"
              strokeWidth={1}
              strokeDasharray="4 4"
            />

            {/* ROC Curve line */}
            <Line
              name="ROC Curve"
              type="monotone"
              dataKey="tp_rate"
              stroke="#2563eb"
              strokeWidth={2.5}
              dot={false}
              activeDot={false}
            />

            {/* Optimal Point Marker */}
            {scatterData.length > 0 && (
              <Scatter
                name="Optimal Threshold"
                data={scatterData}
                fill="#10b981"
                shape={(props: unknown) => {
                  const { cx, cy } = props as { cx: number; cy: number };
                  return (
                    <g key="optimal-marker">
                      <circle cx={cx} cy={cy} r={8} fill="#10b981" fillOpacity={0.3} className="animate-ping" />
                      <circle cx={cx} cy={cy} r={5} fill="#10b981" stroke="#ffffff" strokeWidth={1.5} />
                    </g>
                  );
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
