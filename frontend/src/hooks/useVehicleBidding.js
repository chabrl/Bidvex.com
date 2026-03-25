import API_BASE from '../config';
/**
 * useVehicleBidding Hook
 * Real-time WebSocket connection for vehicle auctions
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const getWebSocketUrl = () => {
  const backendUrl = API_BASE || '';
  return backendUrl.replace('https://', 'wss://').replace('http://', 'ws://');
};

export const useVehicleBidding = (vehicleId, enabled = true) => {
  const [currentBid, setCurrentBid] = useState(0);
  const [bidCount, setBidCount] = useState(0);
  const [endTime, setEndTime] = useState(null);
  const [reserveMet, setReserveMet] = useState(false);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  const connect = useCallback(() => {
    if (!vehicleId || !enabled) return;
    
    const wsUrl = `${getWebSocketUrl()}/api/ws/vehicle/${vehicleId}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('[VehicleBidding] WebSocket connected');
        setConnected(true);
        
        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'initial_state' || data.type === 'bid_update') {
            if (data.current_bid !== undefined) setCurrentBid(data.current_bid);
            if (data.bid_count !== undefined) setBidCount(data.bid_count);
            if (data.end_time) setEndTime(new Date(data.end_time));
            if (data.reserve_met !== undefined) setReserveMet(data.reserve_met);
            setLastUpdate(new Date());
          }
        } catch (err) {
          console.error('[VehicleBidding] Failed to parse message:', err);
        }
      };
      
      wsRef.current.onclose = (event) => {
        console.log('[VehicleBidding] WebSocket closed', event.code);
        setConnected(false);
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Reconnect after 3 seconds
        if (enabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
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
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
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

  // Calculate time remaining
  const [timeRemaining, setTimeRemaining] = useState(null);
  
  useEffect(() => {
    if (!endTime) return;
    
    const updateTimer = () => {
      const now = new Date();
      const diff = endTime - now;
      
      if (diff <= 0) {
        setTimeRemaining({ ended: true });
        return;
      }
      
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      setTimeRemaining({ days, hours, minutes, seconds, ended: false, total: diff });
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
