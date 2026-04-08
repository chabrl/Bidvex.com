import API_BASE from '../config';
/**
 * useVehicleBidding Hook
 * Real-time WebSocket connection for vehicle auctions
 * Connects to the shared listings WS endpoint.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const getWebSocketUrl = () => {
  const backendUrl = API_BASE || '';
  return backendUrl.replace('/api', '').replace('https://', 'wss://').replace('http://', 'ws://');
};

export const useVehicleBidding = (vehicleId, enabled = true, vehicleData = null) => {
  const [currentBid, setCurrentBid] = useState(0);
  const [bidCount, setBidCount] = useState(0);
  const [endTime, setEndTime] = useState(null);
  const [reserveMet, setReserveMet] = useState(false);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  // Fallback: initialize endTime from vehicle API data if WebSocket hasn't provided it
  useEffect(() => {
    if (!endTime && vehicleData) {
      const endDate = vehicleData.auction_end_date || vehicleData.end_time || vehicleData.end_date;
      if (endDate) {
        setEndTime(new Date(endDate));
      }
    }
  }, [vehicleData, endTime]);

  const connect = useCallback(() => {
    if (!vehicleId || !enabled) return;
    
    // Connect to the shared listings WS endpoint (not a vehicle-specific one)
    const wsUrl = `${getWebSocketUrl()}/api/ws/listings/${vehicleId}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('[VehicleBidding] WebSocket connected');
        setConnected(true);
        
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'PING' }));
          }
        }, 25000);
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'INITIAL_STATE' || data.type === 'BID_UPDATE' || 
              data.type === 'initial_state' || data.type === 'bid_update') {
            // Parse current price/bid
            const price = data.current_price ?? data.current_bid;
            if (price !== undefined) setCurrentBid(price);
            if (data.bid_count !== undefined) setBidCount(data.bid_count);
            
            // Parse end time from multiple possible field names
            const endTimeStr = data.auction_end_date || data.end_time || data.new_end_time;
            if (endTimeStr) setEndTime(new Date(endTimeStr));
            
            if (data.reserve_met !== undefined) setReserveMet(data.reserve_met);
            setLastUpdate(new Date());
          }
          
          if (data.type === 'TIME_EXTENSION') {
            const newEnd = data.new_end_time || data.auction_end_date;
            if (newEnd) setEndTime(new Date(newEnd));
          }
        } catch (err) {
          console.error('[VehicleBidding] Failed to parse message:', err);
        }
      };
      
      wsRef.current.onclose = () => {
        setConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        
        // Silent reconnect
        if (enabled) {
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('[VehicleBidding] WebSocket error:', error);
      };
      
    } catch (err) {
      console.error('[VehicleBidding] Failed to connect:', err);
    }
  }, [vehicleId, enabled]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Timer countdown
  const [timeRemaining, setTimeRemaining] = useState(null);
  
  useEffect(() => {
    if (!endTime) return;
    
    const updateTimer = () => {
      const now = new Date();
      const diff = endTime - now;
      
      if (diff <= 0) {
        setTimeRemaining({ ended: true, days: 0, hours: 0, minutes: 0, seconds: 0 });
        return;
      }
      
      setTimeRemaining({
        days: Math.floor(diff / (1000 * 60 * 60 * 24)),
        hours: Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)),
        minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
        seconds: Math.floor((diff % (1000 * 60)) / 1000),
        ended: false,
        total: diff
      });
    };
    
    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [endTime]);

  return {
    currentBid,
    bidCount,
    endTime,
    timeRemaining,
    reserveMet,
    connected,
    lastUpdate,
  };
};

export default useVehicleBidding;
