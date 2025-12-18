import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

// Check if debug mode is enabled (admin or environment variable)
const isDebugMode = () => {
  return process.env.REACT_APP_DEBUG_MODE === 'true' || 
         localStorage.getItem('debug_mode') === 'true';
};

// Admin-only debug toast helper
const debugToast = (message, type = 'info', user = null) => {
  // Only show debug toasts for admin users or when debug mode is enabled
  const isAdmin = user?.role === 'admin' || user?.email?.includes('@admin.');
  if (!isAdmin && !isDebugMode()) return;
  
  const prefix = '🔧 DEBUG: ';
  const options = { duration: 3000, id: `debug-${Date.now()}` };
  
  switch(type) {
    case 'success':
      toast.success(prefix + message, options);
      break;
    case 'error':
      toast.error(prefix + message, options);
      break;
    case 'warning':
      toast.warning(prefix + message, options);
      break;
    default:
      toast.info(prefix + message, options);
  }
};

/**
 * Real-time bidding hook with WebSocket connection
 * Provides instant bid updates with <200ms latency
 * Automatically handles reconnection and fallback polling
 * Includes admin-only debug toasts for troubleshooting
 */
export const useRealtimeBidding = (listingId) => {
  const { user } = useAuth();
  const [currentPrice, setCurrentPrice] = useState(null);
  const [bidCount, setBidCount] = useState(0);
  const [highestBidderId, setHighestBidderId] = useState(null);
  const [bidStatus, setBidStatus] = useState('VIEWER'); // LEADING, OUTBID, VIEWER, NO_BIDS
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connectionHealth, setConnectionHealth] = useState('connecting'); // connecting, healthy, degraded, disconnected
  const [auctionEndDate, setAuctionEndDate] = useState(null); // For anti-sniping time extensions
  const [auctionEndEpoch, setAuctionEndEpoch] = useState(null); // Unix timestamp (timezone-safe)
  const [serverTimeOffset, setServerTimeOffset] = useState(0); // Client-server time difference
  const [timeExtended, setTimeExtended] = useState(false); // Flag when time is extended
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const lastPongRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const connectRef = useRef(null); // Ref to store connect function for self-referencing
  const maxReconnectAttempts = 10;

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
  const WS_URL = API_URL.replace('https', 'wss').replace('http', 'ws');

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

    setConnectionHealth('connecting');

    try {
      // Use /api/ws prefix for Kubernetes Ingress routing to backend
      const wsUrl = user 
        ? `${WS_URL}/api/ws/listings/${listingId}?user_id=${user.id}`
        : `${WS_URL}/api/ws/listings/${listingId}`;
      
      console.log('[Bidding] Connecting to WebSocket:', wsUrl);
      debugToast(`Connecting to ${wsUrl.split('?')[0]}...`, 'info', user);
      
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('[Bidding] WebSocket connected');
        setIsConnected(true);
        setConnectionHealth('healthy');
        reconnectAttemptsRef.current = 0;
        lastPongRef.current = Date.now();
        stopFallbackPolling();
        
        debugToast('✅ WebSocket Connected - Live updates active', 'success', user);
        
        // Clear any existing ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Send ping every 20 seconds (as user requested)
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            // Check if we haven't received a pong in 40 seconds (missed 2 pings)
            const timeSinceLastPong = Date.now() - (lastPongRef.current || Date.now());
            if (timeSinceLastPong > 40000) {
              console.warn('[Bidding] No pong received in 40s, connection may be dead');
              setConnectionHealth('degraded');
              debugToast('⚠️ Connection degraded - no heartbeat response', 'warning', user);
              // Force reconnect
              ws.close();
              return;
            }
            
            console.log('[Bidding] Sending PING');
            ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'CONNECTION_ESTABLISHED':
              console.log('[Bidding] Connection established:', data);
              debugToast(`Connection confirmed: ${data.message}`, 'success', user);
              break;
              
            case 'INITIAL_STATE':
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              
              // CRITICAL: Use epoch timestamp for timezone-safe countdown
              // This is immune to browser timezone interpretation issues
              if (data.auction_end_epoch) {
                setAuctionEndEpoch(data.auction_end_epoch);
                // Calculate client-server time offset for accurate countdown
                const clientNow = Math.floor(Date.now() / 1000);
                const serverNow = data.server_time_epoch || clientNow;
                const offset = serverNow - clientNow;
                setServerTimeOffset(offset);
                console.log('[Bidding] ⏱️ Epoch sync:', {
                  auction_end_epoch: data.auction_end_epoch,
                  server_time_epoch: data.server_time_epoch,
                  client_time: clientNow,
                  offset_seconds: offset
                });
                
                // Also set Date object for backwards compatibility
                const endDate = new Date(data.auction_end_epoch * 1000);
                setAuctionEndDate(endDate);
              } else if (data.auction_end_date) {
                // Fallback to ISO string parsing
                const serverEndDate = new Date(data.auction_end_date);
                setAuctionEndDate(serverEndDate);
                console.log('[Bidding] Synced auction end date from ISO string:', data.auction_end_date);
              }
              
              // Check if auction has ended according to server
              if (data.auction_active === false) {
                console.log('[Bidding] Server reports auction has ended');
                setBidStatus('AUCTION_ENDED');
              }
              
              console.log('[Bidding] Initial state received:', data);
              debugToast(`Initial state: $${data.current_price}, ${data.bid_count} bids, active=${data.auction_active}`, 'info', user);
              break;
              
            case 'BID_UPDATE':
              // Real-time bid update (<200ms target)
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              
              // Handle anti-sniping time extension (use epoch timestamp if available)
              if (data.time_extended) {
                if (data.new_auction_end_epoch) {
                  // Use timezone-safe epoch timestamp
                  setAuctionEndEpoch(data.new_auction_end_epoch);
                  setAuctionEndDate(new Date(data.new_auction_end_epoch * 1000));
                  // Update server time offset
                  if (data.server_time_epoch) {
                    const clientNow = Math.floor(Date.now() / 1000);
                    setServerTimeOffset(data.server_time_epoch - clientNow);
                  }
                  console.log('[Bidding] ⏰ Time extended (epoch):', data.new_auction_end_epoch);
                } else if (data.new_auction_end) {
                  // Fallback to ISO string
                  setAuctionEndDate(new Date(data.new_auction_end));
                  console.log('[Bidding] ⏰ Time extended (ISO):', data.new_auction_end);
                }
                setTimeExtended(true);
                
                // Show time extension notification to all users
                toast.info('⏰ Auction Extended!', {
                  description: 'A last-minute bid has extended the auction by 2 minutes.',
                  duration: 5000,
                  id: 'time-extension'
                });
              }
              
              const latency = Date.now() - new Date(data.timestamp).getTime();
              console.log('[Bidding] Real-time update:', {
                price: data.current_price,
                status: data.bid_status,
                latency: latency + 'ms',
                timeExtended: data.time_extended
              });
              
              // Admin-only debug toast for bid updates
              debugToast(`📥 Incoming Bid: $${data.current_price} (${latency}ms latency) - Status: ${data.bid_status}${data.time_extended ? ' ⏰ TIME EXTENDED' : ''}`, 'info', user);
              
              // Show toast notification for all users
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
              
            case 'TIME_EXTENSION':
              // Handle dedicated time extension message (for lot-based auctions)
              if (data.new_end_time) {
                setAuctionEndDate(new Date(data.new_end_time));
                setTimeExtended(true);
                console.log('[Bidding] ⏰ TIME_EXTENSION received:', data);
                
                toast.info('⏰ Auction Extended!', {
                  description: `Lot ${data.lot_number || ''} extended by 2 minutes due to bidding activity.`,
                  duration: 5000,
                  id: 'time-extension'
                });
              }
              break;
              
            case 'HEARTBEAT':
              lastPongRef.current = Date.now();
              setConnectionHealth('healthy');
              console.log('[Bidding] Heartbeat received from server');
              break;
              
            case 'PONG':
              lastPongRef.current = Date.now();
              setConnectionHealth('healthy');
              console.log('[Bidding] Pong received');
              break;
              
            default:
              console.log('[Bidding] Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('[Bidding] Error parsing message:', error);
          debugToast(`Parse error: ${error.message}`, 'error', user);
        }
      };

      ws.onerror = (error) => {
        console.error('[Bidding] WebSocket error:', error);
        setIsConnected(false);
        setConnectionHealth('disconnected');
        debugToast(`WebSocket error - check console`, 'error', user);
      };

      ws.onclose = (event) => {
        console.log('[Bidding] WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        setConnectionHealth('disconnected');
        
        debugToast(`Connection closed (code: ${event.code})`, 'warning', user);
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        // Start fallback polling immediately
        startFallbackPolling();
        
        // Attempt to reconnect with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`[Bidding] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            // Use ref to call connect to avoid self-reference issue
            if (connectRef.current) {
              connectRef.current();
            }
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
      setConnectionHealth('disconnected');
      startFallbackPolling();
    }
  }, [listingId, user, WS_URL, startFallbackPolling, stopFallbackPolling]);
  
  // Update ref when connect changes - use useEffect to avoid updating during render
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    
    stopFallbackPolling();
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionHealth('disconnected');
  }, [stopFallbackPolling]);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (listingId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [listingId, connect, disconnect]); // Re-connect if listingId changes

  // Reconnect if user logs in/out
  useEffect(() => {
    if (wsRef.current) {
      disconnect();
      setTimeout(() => {
        if (connectRef.current) {
          connectRef.current();
        }
      }, 100);
    }
  }, [user?.id, disconnect]);

  return {
    currentPrice,
    bidCount,
    highestBidderId,
    bidStatus,
    isConnected,
    connectionHealth,
    lastUpdate,
    auctionEndDate,      // Date object (for react-countdown)
    auctionEndEpoch,     // Unix timestamp (timezone-safe, primary source)
    serverTimeOffset,    // Client-server time difference in seconds
    timeExtended,        // Flag indicating time was extended
    reconnect: connect
  };
};

export default useRealtimeBidding;
