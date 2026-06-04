import { useEffect, useCallback } from 'react';
import client from '../api/client';
import { useStore } from '../store';

export default function useDriftData(modelId: number | null, days = 7) {
  const setDriftEvents = useStore((state) => state.setDriftEvents);
  const driftEvents = useStore((state) => state.driftEvents);
  const isLoading = useStore((state) => state.isLoadingDrift);
  const setLoading = useStore((state) => state.setDriftLoading);
  const error = useStore((state) => state.driftError);
  const setError = useStore((state) => state.setDriftError);

  const fetchDriftData = useCallback(async () => {
    if (!modelId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await client.get(`/api/drift/`, {
        params: {
          model_id: modelId,
          days: days,
          limit: 100,
        },
      });
      setDriftEvents(response.data.events);
    } catch (err) {
      console.error('Failed to fetch drift events:', err);
      const errorMsg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to load drift events';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [modelId, days, setDriftEvents, setLoading, setError]);

  useEffect(() => {
    fetchDriftData();
  }, [fetchDriftData]);

  return {
    data: driftEvents.filter((e) => e.model_id === modelId),
    isLoading,
    error,
    refetch: fetchDriftData,
  };
}
