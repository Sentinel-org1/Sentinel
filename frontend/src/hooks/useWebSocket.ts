import { useEffect, useRef } from 'react';
import { useStore } from '../store';

export default function useWebSocket(modelId: number | null) {
  const token = useStore((state) => state.token);
  const addDriftEvent = useStore((state) => state.addDriftEvent);
  const addAlert = useStore((state) => state.addAlert);
  const setWsStatus = useStore((state) => state.setWsStatus);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);

  useEffect(() => {
    let shouldReconnect = true;
    if (!modelId || !token) {
      if (wsRef.current) {
        wsRef.current.close();
      }
      setWsStatus('disconnected');
      return;
    }

    function connect() {
      if (wsRef.current) {
        wsRef.current.close();
      }

      setWsStatus('connecting');
      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // Use the current host so Vite proxy (or production reverse-proxy) handles forwarding
      const wsUrl = `${wsProto}//${window.location.host}/ws/stream?model_id=${modelId}&token=${token}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
        reconnectAttemptsRef.current = 0;
        console.log(`WebSocket connected for model ${modelId}`);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'ping') {
            // Heartbeat from server
            return;
          }

          if (data.detector && data.drift_type) {
            // This is a drift event broadcast
            const driftEvent = {
              id: Date.now(), // Fallback local ID if broadcast doesn't have it
              model_id: data.model_id,
              detector: data.detector,
              metric_name: data.metric_name || null,
              score: data.score || 0.0,
              threshold: data.threshold || 0.25,
              drift_type: data.drift_type,
              severity: data.severity || 'warn',
              shap_attribution: data.shap_attribution || null,
              detected_at: data.timestamp || new Date().toISOString(),
              ...data,
            };
            addDriftEvent(driftEvent);
          } else if (data.drift_event_id && data.severity) {
            // This is an alert broadcast
            const alert = {
              id: data.id || Date.now(),
              drift_event_id: data.drift_event_id,
              model_id: data.model_id,
              severity: data.severity,
              status: data.status || 'open',
              suppressed: data.suppressed || false,
              created_at: data.created_at || new Date().toISOString(),
              updated_at: data.updated_at || new Date().toISOString(),
            };
            addAlert(alert);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onclose = (event) => {
        setWsStatus('disconnected');
        wsRef.current = null;
        console.log(`WebSocket closed: ${event.reason} (code ${event.code})`);

        if (!shouldReconnect) {
          return;
        }

        // Close code 4001 indicates auth failure — do not auto-reconnect
        if (event.code === 4001) {
          console.error('WebSocket authentication failed.');
          return;
        }

        // Reconnect with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;
        
        console.log(`Retrying WebSocket connection in ${delay}ms...`);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = (err) => {
        console.error('WebSocket encountered an error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      shouldReconnect = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [modelId, token, addDriftEvent, addAlert, setWsStatus]);

  return wsRef.current;
}
