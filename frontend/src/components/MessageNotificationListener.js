import API_BASE from '../config';
import { useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { MessageCircle } from 'lucide-react';

/**
 * Global WebSocket listener for message notifications.
 * Shows toast notifications when user receives messages outside of the messages page.
 *
 * Resilience:
 *   - Max 5 reconnect attempts with exponential backoff (5s → 80s).
 *   - Errors logged at debug level (not error) — WS may not be routed in all envs.
 *   - All event handlers wrapped in try/catch so a malformed payload never throws.
 */
const MessageNotificationListener = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const giveUpRef = useRef(false);

  const API_URL = API_BASE || 'http://localhost:8001';
  const WS_BASE = API_URL.replace('/api', '').replace('https', 'wss').replace('http', 'ws');

  useEffect(() => {
    if (!user?.id) return;

    // Prevent duplicate connections
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    reconnectAttemptsRef.current = 0;
    giveUpRef.current = false;

    const scheduleReconnect = () => {
      if (giveUpRef.current) return;
      reconnectAttemptsRef.current += 1;
      if (reconnectAttemptsRef.current > 5) {
        // Quietly stop trying — WS may not be routed in this environment.
        // Real-time notifications won't show, but core app continues to work.
        giveUpRef.current = true;
        if (process.env.NODE_ENV === 'development') {
          console.debug('[NotificationListener] Giving up after 5 attempts — real-time notifications disabled.');
        }
        return;
      }
      const delay = Math.min(80000, 5000 * 2 ** (reconnectAttemptsRef.current - 1));
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    };

    const connect = () => {
      if (giveUpRef.current) return;
      // Guard against multiple simultaneous connections
      if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

      try {
        const ws = new WebSocket(`${WS_BASE}/api/ws/messages/${user.id}`);

        ws.onopen = () => {
          reconnectAttemptsRef.current = 0;
          if (process.env.NODE_ENV === 'development') {
            console.debug('[NotificationListener] Connected');
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            // Handle new message notifications
            if (data.type === 'new_message_notification' || data.type === 'new_message') {
              // Only show toast if not already on messages page
              if (!location.pathname.startsWith('/messages')) {
                const senderName = data.sender_name || 'Someone';
                const preview = data.preview || data.message?.content?.slice(0, 50) || 'New message';

                toast.info(
                  <div
                    className="flex items-start gap-3 cursor-pointer"
                    onClick={() => {
                      try {
                        navigate(`/messages?conversation=${data.conversation_id}`);
                        toast.dismiss();
                      } catch { /* swallow nav errors */ }
                    }}
                  >
                    <div className="p-2 bg-primary/10 rounded-full">
                      <MessageCircle className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">New message from {senderName}</p>
                      <p className="text-xs text-muted-foreground line-clamp-2">{preview}</p>
                    </div>
                  </div>,
                  {
                    duration: 5000,
                    id: `msg-${data.conversation_id}`,
                  }
                );
              }
            }
          } catch {
            // Malformed payload — swallow silently. Never break the app for a bad WS frame.
          }
        };

        ws.onclose = () => {
          if (process.env.NODE_ENV === 'development') {
            console.debug('[NotificationListener] Disconnected, scheduling reconnect…');
          }
          scheduleReconnect();
        };

        ws.onerror = () => {
          // Silently absorb. WS errors are common in dev/preview and Cloudflare-fronted envs;
          // surfacing them as console errors confuses users (visible in DevTools) for no benefit.
          if (process.env.NODE_ENV === 'development') {
            console.debug('[NotificationListener] WS error (suppressed)');
          }
          // ws.onclose will fire next and trigger reconnect logic.
        };

        wsRef.current = ws;
      } catch {
        // Constructor itself can throw on invalid URL — back off & retry.
        scheduleReconnect();
      }
    };

    connect();

    return () => {
      giveUpRef.current = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        try { wsRef.current.close(); } catch { /* ignore */ }
      }
    };
  }, [user?.id, WS_BASE, navigate, location.pathname]);

  return null; // This component doesn't render anything
};

export default MessageNotificationListener;
