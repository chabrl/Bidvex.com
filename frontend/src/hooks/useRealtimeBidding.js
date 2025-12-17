import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

/**
 * Real-time bidding hook with WebSocket connection
 * Provides instant bid updates with <200ms latency
 * Automatically handles reconnection and fallback polling
 */
export const useRealtimeBidding = (listingId) => {
  const { user } = useAuth();
  const [currentPrice, setCurrentPrice] = useState(null);
  const [bidCount, setB idCount] = useState(0);
  const [highestBidderId, setHighestBidderId] = useState(null);
  const [bidStatus, setBidStatus] = useState('VIEWER'); // LEADING, OUTBID, VIEWER, NO_BIDS
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
  const WS_URL = API_URL.replace('http', 'ws');

  // Fallback polling when WebSocket is disconnected
  const startFallbackPolling = useCallback(() => {
    if (pollingIntervalRef.current) return;

    console.log('[Bidding] Starting fallback polling (3s interval)');
    
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_URL}/api/listings/${listingId}`);
        if (response.ok) {
          const listing = await response.json();
          setCurrentPrice(listing.current_price);
          setBidCount(listing.bid_count || 0);
          setHighestBidderId(listing.highest_bidder_id || null);
          
          // Determine status
          if (user && user.id === listing.highest_bidder_id) {
            setBidStatus('LEADING');
          } else if (listing.highest_bidder_id) {
            setBidStatus('OUTBID');
          } else {
            setBidStatus('NO_BIDS');
          }
          
          setLastUpdate(new Date().toISOString());
        }
      } catch (error) {
        console.error('[Bidding] Polling error:', error);
      }
    }, 3000); // Poll every 3 seconds as per requirements
  }, [listingId, user, API_URL]);

  const stopFallbackPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      console.log('[Bidding] Stopped fallback polling');
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      const wsUrl = user 
        ? `${WS_URL}/ws/listings/${listingId}?user_id=${user.id}`
        : `${WS_URL}/ws/listings/${listingId}`;
      
      console.log('[Bidding] Connecting to WebSocket:', wsUrl);
      
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('[Bidding] WebSocket connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        stopFallbackPolling();
        
        // Send ping every 25 seconds to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING' }));
          }
        }, 25000);
        
        ws.pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'CONNECTION_ESTABLISHED':
              console.log('[Bidding] Connection established');
              break;
              
            case 'INITIAL_STATE':
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              console.log('[Bidding] Initial state received:', data);
              break;
              
            case 'BID_UPDATE':
              // Real-time bid update (<200ms target)
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              
              console.log('[Bidding] Real-time update:', {
                price: data.current_price,
                status: data.bid_status,
                latency: Date.now() - new Date(data.timestamp).getTime() + 'ms'
              });
              
              // Show toast notification
              if (data.bid_status === 'OUTBID' && user) {
                toast.warning('You\'ve been outbid!', {
                  description: `New bid: $${data.current_price}`,
                  duration: 5000
                });
              } else if (data.bid_status === 'LEADING' && user) {
                toast.success('You\'re now the highest bidder!', {
                  duration: 3000
                });
              }
              break;
              
            case 'HEARTBEAT':
            case 'PONG':
              // Connection health check
              break;
              
            default:
              console.log('[Bidding] Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('[Bidding] Error parsing message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[Bidding] WebSocket error:', error);
        setIsConnected(false);
      };

      ws.onclose = (event) => {
        console.log('[Bidding] WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        
        // Clear ping interval
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval);
        }
        
        // Start fallback polling immediately
        startFallbackPolling();
        
        // Attempt to reconnect with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`[Bidding] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
          
          toast.error('Live Connection Lost - Reconnecting...', {
            duration: 3000,
            id: 'ws-reconnect'
          });
        } else {
          toast.error('Unable to establish real-time connection. Using polling mode.', {
            duration: 5000
          });
        }
      };

      wsRef.current = ws;
      
    } catch (error) {
      console.error('[Bidding] Error creating WebSocket:', error);
      setIsConnected(false);
      startFallbackPolling();
    }
  }, [listingId, user, WS_URL, startFallbackPolling, stopFallbackPolling, API_URL]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    stopFallbackPolling();
    
    if (wsRef.current) {
      if (wsRef.current.pingInterval) {
        clearInterval(wsRef.current.pingInterval);
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, [stopFallbackPolling]);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (listingId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [listingId]); // Re-connect if listingId changes

  // Reconnect if user logs in/out
  useEffect(() => {
    if (wsRef.current) {
      disconnect();
      setTimeout(connect, 100);
    }
  }, [user?.id]);

  return {
    currentPrice,
    bidCount,
    highestBidderId,
    bidStatus,
    isConnected,
    lastUpdate,
    reconnect: connect
  };
};

export default useRealtimeBidding;
