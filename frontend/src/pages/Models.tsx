import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import client from '../api/client';
import { useStore, Model } from '../store';
import Table, { Column } from '../components/ui/Table';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';

export default function Models() {
  const models = useStore((state) => state.models);
  const setModels = useStore((state) => state.setModels);
  const isLoading = useStore((state) => state.isLoadingModels);
  const setLoading = useStore((state) => state.setModelsLoading);
  const error = useStore((state) => state.modelsError);
  const setError = useStore((state) => state.setModelsError);
  const navigate = useNavigate();

  // Create Model Form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newVersion, setNewVersion] = useState('1.0.0');
  const [newTaskType, setNewTaskType] = useState<'classification' | 'regression' | 'ranking'>('classification');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.get('/api/models/');
      setModels(response.data);
    } catch (err) {
      console.error('Failed to fetch models:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to fetch registered models';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [setModels, setLoading, setError]);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleCreateModel = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await client.post('/api/models/', {
        name: newName,
        version: newVersion,
        task_type: newTaskType,
        config_json: {},
      });
      // Append model and close form
      setModels([response.data, ...models]);
      setNewName('');
      setShowAddForm(false);
    } catch (err) {
      console.error('Failed to create model:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to create model registry entry';
      alert(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const columns: Column<Model>[] = [
    {
      header: 'ID',
      accessor: (row: Model) => <span className="text-slate-500">#{row.id}</span>,
    },
    {
      header: 'Model Name',
      accessor: 'name',
    },
    {
      header: 'Version',
      accessor: (row: Model) => <Badge variant="default">{row.version}</Badge>,
    },
    {
      header: 'Task Type',
      accessor: (row: Model) => <span className="uppercase text-xs font-semibold text-slate-400">{row.task_type}</span>,
    },
    {
      header: 'Status',
      accessor: (row: Model) => {
        const variants = {
          active: 'success' as const,
          deprecated: 'warn' as const,
          archived: 'default' as const,
        };
        return <Badge variant={variants[row.status]}>{row.status}</Badge>;
      },
    },
    {
      header: 'Actions',
      accessor: (row: Model) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/models/${row.id}`);
          }}
        >
          View Dashboard
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6 font-sans">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight">Models Registry</h1>
          <p className="text-xs text-slate-450 mt-1">Register, configure, and inspect production ML models</p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? 'Cancel' : 'Register Model'}
        </Button>
      </div>

      {showAddForm && (
        <Card title="Register New Model" subtitle="Create metadata record to begin ingestion and baselines" hoverEffect={false} className="max-w-2xl">
          <form onSubmit={handleCreateModel} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-450">Model Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. FraudDetectionModel"
                  className="w-full bg-slate-950/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg px-4 py-2.5 text-sm text-slate-200 outline-none transition-all"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-450">Version String</label>
                <input
                  type="text"
                  required
                  value={newVersion}
                  onChange={(e) => setNewVersion(e.target.value)}
                  placeholder="e.g. 1.0.0"
                  className="w-full bg-slate-950/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg px-4 py-2.5 text-sm text-slate-200 outline-none transition-all"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-450">Prediction Task Type</label>
              <select
                value={newTaskType}
                title="Prediction Task Type"
                onChange={(e) => setNewTaskType(e.target.value as 'classification' | 'regression' | 'ranking')}
                className="w-full bg-slate-950/60 border border-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 rounded-lg px-4 py-2.5 text-sm text-slate-200 outline-none transition-all"
              >
                <option value="classification">Classification (Binary / Multi)</option>
                <option value="regression">Regression</option>
                <option value="ranking">Ranking</option>
              </select>
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" variant="primary" isLoading={isSubmitting}>
                Save Model Entry
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl">
          {error}
        </div>
      )}

      <Table
        columns={columns}
        data={models}
        isLoading={isLoading}
        emptyMessage="No registered models found. Register one to get started."
        onRowClick={(row) => navigate(`/models/${row.id}`)}
      />
    </div>
  );
}
