import API_BASE from '../config';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatCurrency } from '../utils/currencyFormatter';

/**
 * Real-time bidding hook with WebSocket connection
 * Provides instant bid updates with <200ms latency
 * Automatically handles reconnection and fallback polling
 */
export const useRealtimeBidding = (listingId) => {
  const { user } = useAuth();
  const [currentPrice, setCurrentPrice] = useState(null);
  const [bidCount, setBidCount] = useState(0);
  const [highestBidderId, setHighestBidderId] = useState(null);
  const [bidStatus, setBidStatus] = useState('VIEWER');
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connectionHealth, setConnectionHealth] = useState('connecting');
  const [auctionEndDate, setAuctionEndDate] = useState(null);
  const [auctionEndEpoch, setAuctionEndEpoch] = useState(null);
  const [serverTimeOffset, setServerTimeOffset] = useState(0);
  const [timeExtended, setTimeExtended] = useState(false);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const lastPongRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const connectRef = useRef(null);
  const maxReconnectAttempts = 10;

  const API_URL = API_BASE || 'http://localhost:8001';
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
    }, 3000);
  }, [listingId, user, API_URL]);

  const stopFallbackPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setConnectionHealth('connecting');

    try {
      const wsUrl = user 
        ? `${WS_URL}/api/ws/listings/${listingId}?user_id=${user.id}`
        : `${WS_URL}/api/ws/listings/${listingId}`;
      
      console.log('[Bidding] Connecting:', wsUrl.split('?')[0]);
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('[Bidding] WebSocket connected');
        setIsConnected(true);
        setConnectionHealth('healthy');
        reconnectAttemptsRef.current = 0;
        lastPongRef.current = Date.now();
        stopFallbackPolling();
        
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            const timeSinceLastPong = Date.now() - (lastPongRef.current || Date.now());
            if (timeSinceLastPong > 40000) {
              console.warn('[Bidding] No pong in 40s, reconnecting...');
              setConnectionHealth('degraded');
              ws.close();
              return;
            }
            ws.send(JSON.stringify({ type: 'PING', timestamp: Date.now() }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'CONNECTION_ESTABLISHED':
              console.log('[Bidding] Connection established:', data.message);
              break;
              
            case 'INITIAL_STATE':
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              
              if (data.auction_end_epoch) {
                setAuctionEndEpoch(data.auction_end_epoch);
                const clientNow = Math.floor(Date.now() / 1000);
                const serverNow = data.server_time_epoch || clientNow;
                setServerTimeOffset(serverNow - clientNow);
                setAuctionEndDate(new Date(data.auction_end_epoch * 1000));
              } else if (data.auction_end_date) {
                setAuctionEndDate(new Date(data.auction_end_date));
              }
              
              if (data.auction_active === false) {
                setBidStatus('AUCTION_ENDED');
              }
              
              console.log('[Bidding] Initial state:', { price: data.current_price, bids: data.bid_count, active: data.auction_active });
              break;
              
            case 'BID_UPDATE':
              setCurrentPrice(data.current_price);
              setBidCount(data.bid_count);
              setHighestBidderId(data.highest_bidder_id);
              setBidStatus(data.bid_status);
              setLastUpdate(data.timestamp);
              
              if (data.time_extended) {
                if (data.new_auction_end_epoch) {
                  setAuctionEndEpoch(data.new_auction_end_epoch);
                  setAuctionEndDate(new Date(data.new_auction_end_epoch * 1000));
                  if (data.server_time_epoch) {
                    const clientNow = Math.floor(Date.now() / 1000);
                    setServerTimeOffset(data.server_time_epoch - clientNow);
                  }
                } else if (data.new_auction_end) {
                  setAuctionEndDate(new Date(data.new_auction_end));
                }
                setTimeExtended(true);
                toast.info('Auction Extended!', {
                  description: 'A last-minute bid has extended the auction by 2 minutes.',
                  duration: 5000,
                  id: 'time-extension'
                });
              }
              
              // User-facing notifications only
              if (data.bid_status === 'OUTBID' && user) {
                toast.warning('You\'ve been outbid!', {
                  description: `New bid: ${formatCurrency(data.current_price)}`,
                  duration: 5000
                });
              } else if (data.bid_status === 'LEADING' && user) {
                toast.success('You\'re now the highest bidder!', { duration: 3000 });
              }
              break;
              
            case 'TIME_EXTENSION':
              if (data.new_end_time) {
                setAuctionEndDate(new Date(data.new_end_time));
                setTimeExtended(true);
                toast.info('Auction Extended!', {
                  description: `Lot ${data.lot_number || ''} extended by 2 minutes due to bidding activity.`,
                  duration: 5000,
                  id: 'time-extension'
                });
              }
              break;
              
            case 'HEARTBEAT':
            case 'PONG':
              lastPongRef.current = Date.now();
              setConnectionHealth('healthy');
              break;
              
            default:
              console.log('[Bidding] Unknown message:', data.type);
          }
        } catch (error) {
          console.error('[Bidding] Parse error:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[Bidding] WebSocket error:', error);
        setIsConnected(false);
        setConnectionHealth('disconnected');
      };

      ws.onclose = (event) => {
        console.log('[Bidding] WebSocket closed:', event.code);
        setIsConnected(false);
        setConnectionHealth('disconnected');
        
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        
        startFallbackPolling();
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            if (connectRef.current) connectRef.current();
          }, delay);
          
          // Only show user-facing toast for actual disconnections (not initial connect)
          if (reconnectAttemptsRef.current > 0) {
            toast.error('Live Connection Lost - Reconnecting...', {
              duration: 3000,
              id: 'ws-reconnect'
            });
          }
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
  
  useEffect(() => { connectRef.current = connect; }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) { clearTimeout(reconnectTimeoutRef.current); reconnectTimeoutRef.current = null; }
    if (pingIntervalRef.current) { clearInterval(pingIntervalRef.current); pingIntervalRef.current = null; }
    stopFallbackPolling();
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setIsConnected(false);
    setConnectionHealth('disconnected');
  }, [stopFallbackPolling]);

  useEffect(() => {
    if (listingId) connect();
    return () => disconnect();
  }, [listingId, connect, disconnect]);

  useEffect(() => {
    if (wsRef.current) {
      disconnect();
      setTimeout(() => { if (connectRef.current) connectRef.current(); }, 100);
    }
  }, [user?.id, disconnect]);

  return {
    currentPrice, bidCount, highestBidderId, bidStatus,
    isConnected, connectionHealth, lastUpdate,
    auctionEndDate, auctionEndEpoch, serverTimeOffset, timeExtended,
    reconnect: connect
  };
};

export default useRealtimeBidding;
