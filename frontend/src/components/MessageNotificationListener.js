import { useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { MessageCircle } from 'lucide-react';

/**
 * Global WebSocket listener for message notifications.
 * Shows toast notifications when user receives messages outside of the messages page.
 */
const MessageNotificationListener = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
  const WS_URL = API_URL.replace('https', 'wss').replace('http', 'ws');

  useEffect(() => {
    if (!user?.id) return;

    const connect = () => {
      try {
        // Use the global user notification channel
        const ws = new WebSocket(`${WS_URL}/ws/messages/${user.id}`);
        
        ws.onopen = () => {
          console.log('[NotificationListener] Connected');
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
                      navigate(`/messages?conversation=${data.conversation_id}`);
                      toast.dismiss();
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
          } catch (error) {
            console.error('[NotificationListener] Error parsing message:', error);
          }
        };

        ws.onclose = () => {
          console.log('[NotificationListener] Disconnected, reconnecting in 5s...');
          reconnectTimeoutRef.current = setTimeout(connect, 5000);
        };

        ws.onerror = (error) => {
          console.error('[NotificationListener] Error:', error);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('[NotificationListener] Connection error:', error);
        reconnectTimeoutRef.current = setTimeout(connect, 5000);
      }
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [user?.id, WS_URL, navigate, location.pathname]);

  return null; // This component doesn't render anything
};

export default MessageNotificationListener;
