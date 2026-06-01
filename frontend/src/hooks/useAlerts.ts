import { useEffect, useCallback } from 'react';
import client from '../api/client';
import { useStore } from '../store';

export default function useAlerts(modelId?: number | null) {
  const setAlerts = useStore((state) => state.setAlerts);
  const alerts = useStore((state) => state.alerts);
  const isLoading = useStore((state) => state.isLoadingAlerts);
  const setLoading = useStore((state) => state.setAlertsLoading);
  const error = useStore((state) => state.alertsError);
  const setError = useStore((state) => state.setAlertsError);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await client.get('/api/alerts/', {
        params: modelId ? { model_id: modelId } : undefined,
      });
      setAlerts(response.data.alerts);
    } catch (err: any) {
      console.error('Failed to fetch alerts:', err);
      setError(err.response?.data?.detail || 'Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [modelId, setAlerts, setLoading, setError]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const filteredAlerts = modelId ? alerts.filter((a) => a.model_id === modelId) : alerts;

  return {
    alerts: filteredAlerts,
    isLoading,
    error,
    refetch: fetchAlerts,
  };
}
