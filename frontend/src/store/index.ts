import { create } from 'zustand';

export interface User {
  id: number;
  email: string;
  is_superuser: boolean;
}

export interface Model {
  id: number;
  name: string;
  version: string;
  task_type: string;
  status: 'active' | 'archived' | 'deprecated';
  config_json?: Record<string, any>;
}

export interface DriftEvent {
  id: number;
  model_id: number;
  detector: string;
  metric_name: string | null;
  score: number;
  threshold: number;
  drift_type: string | null;
  severity: 'warn' | 'critical' | 'info';
  shap_attribution: Record<string, any> | null;
  detected_at: string;
}

export interface Alert {
  id: number;
  drift_event_id: number;
  model_id: number;
  severity: 'warn' | 'critical' | 'info';
  status: 'open' | 'acknowledged' | 'resolved';
  suppressed: boolean;
  created_at: string;
  updated_at: string;
}

interface AppState {
  // Auth state
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setAuth: (token: string | null, user: User | null) => void;
  logout: () => void;

  // Models state
  models: Model[];
  selectedModelId: number | null;
  isLoadingModels: boolean;
  modelsError: string | null;
  setModels: (models: Model[]) => void;
  setSelectedModelId: (id: number | null) => void;
  setModelsLoading: (isLoading: boolean) => void;
  setModelsError: (error: string | null) => void;

  // Drift state
  driftEvents: DriftEvent[];
  isLoadingDrift: boolean;
  driftError: string | null;
  setDriftEvents: (events: DriftEvent[]) => void;
  addDriftEvent: (event: DriftEvent) => void;
  setDriftLoading: (isLoading: boolean) => void;
  setDriftError: (error: string | null) => void;

  // Alerts state
  alerts: Alert[];
  unreadAlertCount: number;
  isLoadingAlerts: boolean;
  alertsError: string | null;
  setAlerts: (alerts: Alert[]) => void;
  addAlert: (alert: Alert) => void;
  updateAlertStatus: (alertId: number, status: Alert['status']) => void;
  setAlertsLoading: (isLoading: boolean) => void;
  setAlertsError: (error: string | null) => void;

  // WebSocket state
  wsStatus: 'disconnected' | 'connecting' | 'connected';
  setWsStatus: (status: 'disconnected' | 'connecting' | 'connected') => void;
}

export const useStore = create<AppState>((set) => {
  // Load token from localStorage on initialization
  const initialToken = localStorage.getItem('sentinel_token');

  return {
    // Auth
    token: initialToken,
    user: null,
    isAuthenticated: !!initialToken,
    setAuth: (token, user) => {
      if (token) {
        localStorage.setItem('sentinel_token', token);
      } else {
        localStorage.removeItem('sentinel_token');
      }
      set({ token, user, isAuthenticated: !!token });
    },
    logout: () => {
      localStorage.removeItem('sentinel_token');
      set({ token: null, user: null, isAuthenticated: false, selectedModelId: null, driftEvents: [], alerts: [] });
    },

    // Models
    models: [],
    selectedModelId: null,
    isLoadingModels: false,
    modelsError: null,
    setModels: (models) => set({ models }),
    setSelectedModelId: (selectedModelId) => set({ selectedModelId }),
    setModelsLoading: (isLoadingModels) => set({ isLoadingModels }),
    setModelsError: (modelsError) => set({ modelsError }),

    // Drift
    driftEvents: [],
    isLoadingDrift: false,
    driftError: null,
    setDriftEvents: (driftEvents) => set({ driftEvents }),
    addDriftEvent: (event) => set((state) => ({ driftEvents: [event, ...state.driftEvents] })),
    setDriftLoading: (isLoadingDrift) => set({ isLoadingDrift }),
    setDriftError: (driftError) => set({ driftError }),

    // Alerts
    alerts: [],
    unreadAlertCount: 0,
    isLoadingAlerts: false,
    alertsError: null,
    setAlerts: (alerts) => {
      const unreadCount = alerts.filter((a) => a.status === 'open').length;
      set({ alerts, unreadAlertCount: unreadCount });
    },
    addAlert: (alert) =>
      set((state) => {
        const isDuplicate = state.alerts.some((a) => a.id === alert.id);
        if (isDuplicate) return {};
        const newAlerts = [alert, ...state.alerts];
        const unreadCount = newAlerts.filter((a) => a.status === 'open').length;
        return { alerts: newAlerts, unreadAlertCount: unreadCount };
      }),
    updateAlertStatus: (alertId, status) =>
      set((state) => {
        const newAlerts = state.alerts.map((a) =>
          a.id === alertId ? { ...a, status, updated_at: new Date().toISOString() } : a
        );
        const unreadCount = newAlerts.filter((a) => a.status === 'open').length;
        return { alerts: newAlerts, unreadAlertCount: unreadCount };
      }),
    setAlertsLoading: (isLoadingAlerts) => set({ isLoadingAlerts }),
    setAlertsError: (alertsError) => set({ alertsError }),

    // WS
    wsStatus: 'disconnected',
    setWsStatus: (wsStatus) => set({ wsStatus }),
  };
});
