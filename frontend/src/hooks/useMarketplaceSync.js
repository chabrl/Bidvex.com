import { useEffect, useRef, useCallback } from 'react';

/**
 * Global marketplace WebSocket hook.
 * Receives LISTING_UPDATE events (bid changes, timer extensions)
 * and calls `onUpdate(msg)` so parent components can patch their card state.
 */
const useMarketplaceSync = (onUpdate) => {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const connect = useCallback(() => {
    const base = process.env.REACT_APP_BACKEND_URL || '';
    const wsUrl = base.replace(/^http/, 'ws') + '/api/ws/marketplace';

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        wsRef.current = ws;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'LISTING_UPDATE' && onUpdateRef.current) {
            onUpdateRef.current(data);
          }
        } catch { /* ignore non-json */ }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnect after 5s
        reconnectTimer.current = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    connect();
    // Keep-alive ping every 25s
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'PING' }));
      }
    }, 25000);

    return () => {
      clearInterval(ping);
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);
};

export default useMarketplaceSync;
