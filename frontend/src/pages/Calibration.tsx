import React, { useEffect, useState } from 'react';
import client from '../api/client';
import { useStore } from '../store';
import CalibrationROC from '../components/charts/CalibrationROC';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';

export default function Calibration() {
  const models = useStore((state) => state.models);
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null);
  interface CalibrationPoint {
    threshold: number;
    tp_rate: number;
    fp_rate: number;
    youden_j: number;
  }

  interface CalibrationData {
    points: CalibrationPoint[];
    optimal_threshold: number;
    auc: number;
  }

  const [calibrationData, setCalibrationData] = useState<CalibrationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Set default model on models load
  useEffect(() => {
    if (models.length > 0 && !selectedModelId) {
      setSelectedModelId(models[0].id);
    }
  }, [models, selectedModelId]);

  const fetchCalibration = async (modelId: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await client.get(`/api/models/${modelId}/calibration`);
      setCalibrationData(response.data);
    } catch (err) {
      console.error('Failed to fetch calibration curve:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to load calibration data';
      setError(errorMsg);
      setCalibrationData(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (selectedModelId) {
      fetchCalibration(selectedModelId);
    }
  }, [selectedModelId]);

  const handleGenerateCalibration = async () => {
    if (!selectedModelId) return;
    setIsGenerating(true);
    setError(null);
    try {
      const response = await client.post(`/api/models/${selectedModelId}/calibration`);
      setCalibrationData(response.data);
      alert('Calibration report generated and saved successfully.');
    } catch (err) {
      console.error('Failed to generate calibration:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to generate calibration curve';
      setError(errorMsg);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      <div>
        <h1 className="text-2xl font-black text-slate-100 tracking-tight">Drift Calibration Tuning</h1>
        <p className="text-xs text-slate-450 mt-1">
          Tune alert thresholds using Youden's J statistic calculated against simulated true/false positive rates
        </p>
      </div>

      <div className="flex flex-wrap gap-4 items-center justify-between bg-slate-900/40 p-4 border border-slate-800 rounded-xl">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Select Model</label>
          <select
            value={selectedModelId || ''}
            title="Select Model"
            onChange={(e) => {
              const val = e.target.value;
              setSelectedModelId(val ? parseInt(val, 10) : null);
            }}
            className="bg-slate-950 border border-slate-800 focus:border-blue-500 rounded-lg px-3 py-1.5 text-xs text-slate-300 outline-none transition-all"
          >
            <option value="" disabled>Select a model...</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} (V{m.version})
              </option>
            ))}
          </select>
        </div>

        {selectedModelId && (
          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateCalibration}
            isLoading={isGenerating}
          >
            Run Threshold Calibration
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="h-96 flex items-center justify-center">
          <Spinner size="lg" />
        </div>
      ) : error ? (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-450 rounded-xl">
          <h4 className="font-bold text-sm">Calibration Error</h4>
          <p className="text-xs mt-1">{error}</p>
        </div>
      ) : calibrationData && calibrationData.points && calibrationData.points.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-4">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider px-1">ROC Curve Visualization</h3>
            <CalibrationROC
              points={calibrationData.points}
              optimalThreshold={calibrationData.optimal_threshold}
              auc={calibrationData.auc}
            />
          </div>

          <div className="space-y-6">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider px-1">Tuning Metrics</h3>
            <Card title="Optimal Target Threshold" subtitle="Calculated from ROC curve data" hoverEffect={false}>
              <div className="space-y-4 text-xs">
                <div className="flex justify-between items-center border-b border-slate-850 pb-2">
                  <span className="text-slate-450">AUC (Discriminant Power):</span>
                  <span className="font-bold text-slate-205">{calibrationData.auc?.toFixed(4)}</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-850 pb-2">
                  <span className="text-slate-455">Optimal Drift Threshold:</span>
                  <span className="font-bold text-emerald-450">{calibrationData.optimal_threshold?.toFixed(4)}</span>
                </div>
                <p className="text-[10px] text-slate-500 leading-normal mt-2">
                  The optimal threshold is computed by finding the decision boundary that maximizes the Youden's J statistic:
                  <span className="block font-mono text-[9px] mt-1 text-slate-400">J = Sensitivity + Specificity - 1</span>
                  Setting your alarm cutoff at this level minimizes false positives due to normal variance while maintaining high sensitivity to genuine drift.
                </p>
              </div>
            </Card>
          </div>
        </div>
      ) : (
        <div className="p-12 border border-dashed border-slate-800 rounded-xl text-center text-slate-500 text-xs bg-slate-900/10 max-w-2xl mx-auto">
          <svg className="w-12 h-12 text-slate-650 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
          </svg>
          <h4 className="font-bold text-slate-350 text-sm mb-1">No threshold calibrations computed</h4>
          <p className="text-[10px] text-slate-600 mb-5 max-w-sm mx-auto">
            Threshold calibration requires simulating drift rates against reference baseline feature data. Click 'Run Threshold Calibration' above to perform simulation.
          </p>
        </div>
      )}
    </div>
  );
}
