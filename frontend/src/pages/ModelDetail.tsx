import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import client from '../api/client';
import { useStore, Model } from '../store';
import useWebSocket from '../hooks/useWebSocket';
import useDriftData from '../hooks/useDriftData';
import PSITimeSeries from '../components/charts/PSITimeSeries';
import ShapBar from '../components/charts/ShapBar';
import STLDecomposition from '../components/charts/STLDecomposition';
import DriftEventTimeline from '../components/DriftEventTimeline';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';

export default function ModelDetail() {
  const { id } = useParams<{ id: string }>();
  const modelId = id ? parseInt(id, 10) : null;

  // Global state
  const setSelectedModelId = useStore((state) => state.setSelectedModelId);
  const [model, setModel] = useState<Model | null>(null);
  const [isLoadingModel, setIsLoadingModel] = useState(true);
  const [modelError, setModelError] = useState<string | null>(null);

  // Active tab state
  const [activeTab, setActiveTab] = useState<'drift' | 'shap' | 'stl' | 'thresholds' | 'settings'>('drift');

  // Trigger WS stream connection
  useWebSocket(modelId);

  // Drift data hook
  const { data: driftEvents, refetch: refetchDrift } = useDriftData(modelId, 7);

  interface ThresholdHistoryPoint {
    timestamp?: string;
    score: number;
    ewma_mean?: number;
    ewma_threshold: number;
  }

  interface Threshold {
    id: number;
    detector: string;
    metric_name: string | null;
    ewma_threshold: number;
    ewma_mean?: number;
    ewma_std?: number;
    history?: ThresholdHistoryPoint[];
    stl_decomposition?: {
      trend: number[];
      seasonal: number[];
      residual: number[];
    } | null;
  }

  // Thresholds state
  const [thresholds, setThresholds] = useState<Threshold[]>([]);
  const [isLoadingThresholds, setIsLoadingThresholds] = useState(false);

  // Upload baseline files state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Manual check trigger state
  const [isChecking, setIsChecking] = useState(false);

  const fetchModelDetail = useCallback(async () => {
    if (!modelId) return;
    setIsLoadingModel(true);
    setModelError(null);
    try {
      const response = await client.get(`/api/models/${modelId}`);
      setModel(response.data);
    } catch (err) {
      console.error('Failed to load model details:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to load model details';
      setModelError(errorMsg);
    } finally {
      setIsLoadingModel(false);
    }
  }, [modelId]);

  // Fetch model metadata
  useEffect(() => {
    if (modelId) {
      setSelectedModelId(modelId);
      fetchModelDetail();
    }
    return () => {
      setSelectedModelId(null);
    };
  }, [modelId, setSelectedModelId, fetchModelDetail]);

  // Fetch thresholds history
  const fetchThresholds = useCallback(async () => {
    if (!modelId) return;
    setIsLoadingThresholds(true);
    try {
      const response = await client.get(`/api/models/${modelId}/thresholds`);
      setThresholds(response.data);
    } catch (err) {
      console.error('Failed to fetch thresholds:', err);
    } finally {
      setIsLoadingThresholds(false);
    }
  }, [modelId]);

  useEffect(() => {
    if (activeTab === 'drift' || activeTab === 'thresholds' || activeTab === 'stl') {
      fetchThresholds();
    }
  }, [activeTab, fetchThresholds]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setUploadSuccess(null);
    }
  };

  const handleUploadBaseline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelId || !selectedFile) return;
    setIsUploading(true);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      await client.post(`/api/models/${modelId}/baseline`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setUploadSuccess('Baseline dataset successfully uploaded and processed!');
      setSelectedFile(null);
    } catch (err) {
      console.error('Baseline upload failed:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to upload baseline';
      alert(errorMsg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleTriggerDriftCheck = async () => {
    if (!modelId) return;
    setIsChecking(true);
    try {
      await client.post(`/api/drift/${modelId}/check`);
      alert('Drift detection task enqueued successfully.');
      setTimeout(() => {
        refetchDrift();
      }, 3000);
    } catch (err) {
      console.error('Drift check trigger failed:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to trigger drift check';
      alert(errorMsg);
    } finally {
      setIsChecking(false);
    }
  };

  if (isLoadingModel) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner size="lg" />
      </div>
    );
  }

  if (modelError || !model) {
    return (
      <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-450 rounded-xl max-w-2xl mx-auto mt-8 font-sans">
        <h4 className="font-bold text-sm">Model Ingestion Error</h4>
        <p className="text-xs mt-1 leading-relaxed">{modelError || 'Model registry record empty.'}</p>
        <Link to="/models" className="text-xs text-blue-400 mt-4 block hover:underline">
          &larr; Back to Registry
        </Link>
      </div>
    );
  }

  // Prep PSI chart data
  // Extract psi detector history
  const psiThreshold = thresholds.find((t) => t.detector === 'psi');
  const psiChartPoints = psiThreshold?.history?.map((h) => ({
    timestamp: h.timestamp || new Date().toISOString(),
    score: h.score,
    ewma_mean: h.ewma_mean,
    ewma_threshold: h.ewma_threshold,
  })) || [];

  // Get latest event with SHAP attribution
  const shapEvent = driftEvents.find((e) => e.shap_attribution !== null);
  const shapAttribution = shapEvent?.shap_attribution as { top_movers?: [string, number][] } | null | undefined;
  const shapTopMovers: [string, number][] = shapAttribution?.top_movers || [];

  // STL select
  const stlThreshold = thresholds.find((t) => t.stl_decomposition !== null);

  return (
    <div className="space-y-8 font-sans">
      {/* Model Detail Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
        <div>
          <div className="flex items-center space-x-3">
            <Link to="/models" className="text-slate-500 hover:text-slate-350 transition-colors">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <h1 className="text-2xl font-black text-slate-100 tracking-tight">{model.name}</h1>
            <Badge variant="default" className="text-xs">
              V{model.version}
            </Badge>
          </div>
          <p className="text-xs text-slate-450 mt-1 uppercase font-semibold">
            Task Type: {model.task_type} • Status: {model.status}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Button variant="secondary" size="sm" onClick={handleTriggerDriftCheck} isLoading={isChecking}>
            Trigger Check
          </Button>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="border-b border-slate-800 flex space-x-8">
        {(['drift', 'shap', 'stl', 'thresholds', 'settings'] as const).map((tab) => {
          const labels = {
            drift: 'Drift Metrics',
            shap: 'SHAP Attribution',
            stl: 'STL Decomposition',
            thresholds: 'Adaptive Thresholds',
            settings: 'Upload & Settings',
          };
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3.5 border-b-2 font-semibold text-sm transition-all outline-none ${
                isActive
                  ? 'border-blue-500 text-blue-450'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              }`}
            >
              {labels[tab]}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      {activeTab === 'drift' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">PSI Historical Timeline</h3>
            {isLoadingThresholds ? (
              <div className="h-80 flex items-center justify-center border border-slate-800 rounded-xl bg-slate-900/10">
                <Spinner size="md" />
              </div>
            ) : psiChartPoints.length > 0 ? (
              <PSITimeSeries data={psiChartPoints} />
            ) : (
              <div className="h-80 flex flex-col items-center justify-center border border-dashed border-slate-800 rounded-xl bg-slate-900/10 text-center p-6 text-slate-500 text-xs">
                No historical PSI score runs recorded. Trigger drift check to generate.
              </div>
            )}
          </div>
          <div className="space-y-6">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Drift Events Log</h3>
            <Card hoverEffect={false} className="p-6 max-h-[400px] overflow-y-auto bg-slate-900/30">
              <DriftEventTimeline events={driftEvents} />
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'shap' && (
        <div className="space-y-6 max-w-4xl">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              SHAP Feature Attribution (Δ_SHAP)
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-normal">
              Shows how feature importances changed between baseline and the latest drifted window.
            </p>
          </div>
          {shapTopMovers.length > 0 ? (
            <ShapBar topMovers={shapTopMovers} />
          ) : (
            <div className="p-12 border border-dashed border-slate-800 rounded-xl text-center text-slate-500 text-xs bg-slate-900/10">
              No recent drift events with SHAP attribution. Complete a drift check first.
            </div>
          )}
        </div>
      )}

      {activeTab === 'stl' && (
        <div className="space-y-6 max-w-4xl">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              STL Seasonal Noise Analysis
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-normal">
              Decomposes drift scores to suppress periodic alerts caused by seasonality rather than model failure.
            </p>
          </div>
          {stlThreshold?.stl_decomposition ? (
            <STLDecomposition
              scoreHistory={stlThreshold.history?.map((h) => h.score) || []}
              trend={stlThreshold.stl_decomposition.trend || []}
              seasonal={stlThreshold.stl_decomposition.seasonal || []}
              residual={stlThreshold.stl_decomposition.residual || []}
            />
          ) : (
            <div className="p-12 border border-dashed border-slate-800 rounded-xl text-center text-slate-500 text-xs bg-slate-900/10">
              No STL decomposition data available. Requires a history series of &ge;14 drift check score runs.
            </div>
          )}
        </div>
      )}

      {activeTab === 'thresholds' && (
        <div className="space-y-6 max-w-4xl">
          <div>
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              Adaptive EWMA Thresholds List
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-normal">
              List of configured active drift monitors and their self-tuning thresholds.
            </p>
          </div>
          {thresholds.length === 0 ? (
            <div className="p-12 border border-dashed border-slate-800 rounded-xl text-center text-slate-500 text-xs bg-slate-900/10">
              No threshold statistics generated yet. Run a drift check to initialize.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {thresholds.map((t) => (
                <Card key={t.id} title={`${t.detector.toUpperCase()}: ${t.metric_name || 'prediction'}`} hoverEffect={false}>
                  <div className="space-y-2.5 text-xs">
                    <div className="flex justify-between border-b border-slate-800 pb-2">
                      <span className="text-slate-450">Current Control Limit:</span>
                      <span className="font-bold text-amber-450">{t.ewma_threshold.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-800 pb-2">
                      <span className="text-slate-450">EWMA Mean:</span>
                      <span className="font-semibold text-slate-200">{t.ewma_mean?.toFixed(4) || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between pb-1">
                      <span className="text-slate-450">EWMA Standard Dev:</span>
                      <span className="font-semibold text-slate-200">{t.ewma_std?.toFixed(4) || 'N/A'}</span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'settings' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl">
          {/* Baseline upload */}
          <Card title="Upload Baseline Dataset" subtitle="Provide training samples CSV to initialize reference distributions" hoverEffect={false}>
            <form onSubmit={handleUploadBaseline} className="space-y-4">
              <div className="border border-dashed border-slate-800 hover:border-blue-500/50 rounded-lg p-6 text-center cursor-pointer transition-colors relative">
                <input
                  type="file"
                  accept=".csv"
                  title="Upload Baseline CSV File"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <svg className="w-8 h-8 text-slate-500 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="text-xs text-slate-400 font-semibold block">
                  {selectedFile ? selectedFile.name : 'Select or drop baseline CSV'}
                </span>
                <span className="text-[10px] text-slate-600 mt-1 block">
                  Should contain columns matching prediction features. Max size 10MB.
                </span>
              </div>

              {uploadSuccess && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-450 text-xs rounded-lg font-medium">
                  {uploadSuccess}
                </div>
              )}

              <Button type="submit" variant="primary" className="w-full" disabled={!selectedFile} isLoading={isUploading}>
                Upload and Compute Stats
              </Button>
            </form>
          </Card>

          {/* Model Registry Config */}
          <Card title="Model Configuration" subtitle="Registered model properties and variables" hoverEffect={false}>
            <div className="space-y-4 text-xs font-sans">
              <div className="space-y-1">
                <span className="text-slate-500 font-semibold uppercase tracking-wider block">Model ID</span>
                <p className="text-sm font-semibold text-slate-200">#{model.id}</p>
              </div>
              <div className="space-y-1">
                <span className="text-slate-500 font-semibold uppercase tracking-wider block">Registry Status</span>
                <Badge variant="success">{model.status}</Badge>
              </div>
              <div className="space-y-1">
                <span className="text-slate-500 font-semibold uppercase tracking-wider block">Configuration Metadata</span>
                <pre className="bg-slate-950 border border-slate-850 p-3 rounded-lg text-[10px] text-slate-400 overflow-x-auto">
                  {JSON.stringify(model.config_json || {}, null, 2)}
                </pre>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
