/**
 * Vehicle Auction Context
 * Manages vehicle auction state and API calls
 */

import React, { createContext, useContext, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VehicleAuctionContext = createContext(null);

export const useVehicleAuction = () => {
  const context = useContext(VehicleAuctionContext);
  if (!context) {
    throw new Error('useVehicleAuction must be used within VehicleAuctionProvider');
  }
  return context;
};

export const VehicleAuctionProvider = ({ children }) => {
  const { token, user } = useAuth();
  const [sellerProfile, setSellerProfile] = useState(null);
  const [loading, setLoading] = useState(false);

  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  // ============= VIN DECODER =============
  const decodeVIN = useCallback(async (vin) => {
    try {
      const response = await axios.get(`${API}/vehicles/decode-vin/${vin}`, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to decode VIN' 
      };
    }
  }, [getAuthHeaders]);

  // ============= SELLER MANAGEMENT =============
  const registerAsSeller = useCallback(async (sellerData) => {
    try {
      const response = await axios.post(`${API}/vehicle-sellers/register`, sellerData, {
        headers: getAuthHeaders(),
      });
      setSellerProfile(response.data);
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Registration failed' 
      };
    }
  }, [getAuthHeaders]);

  const getMySellerProfile = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/vehicle-sellers/me`, {
        headers: getAuthHeaders(),
      });
      setSellerProfile(response.data);
      return { success: true, data: response.data };
    } catch (error) {
      if (error.response?.status === 404) {
        return { success: false, notRegistered: true };
      }
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to get profile' 
      };
    }
  }, [getAuthHeaders]);

  const uploadSellerDocument = useCallback(async (documentType, file) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await axios.post(
        `${API}/vehicle-sellers/documents?document_type=${documentType}`,
        formData,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } }
      );
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Upload failed' 
      };
    }
  }, [token]);

  // ============= VEHICLE LISTINGS =============
  const createVehicleListing = useCallback(async (listingData) => {
    try {
      const response = await axios.post(`${API}/vehicles`, listingData, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to create listing' 
      };
    }
  }, [getAuthHeaders]);

  const uploadVehicleMedia = useCallback(async (vehicleId, category, file, caption = null) => {
    const formData = new FormData();
    formData.append('file', file);
    if (caption) formData.append('caption', caption);
    try {
      const response = await axios.post(
        `${API}/vehicles/${vehicleId}/media?category=${category}`,
        formData,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } }
      );
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Upload failed' 
      };
    }
  }, [token]);

  const submitVehicleForApproval = useCallback(async (vehicleId) => {
    try {
      const response = await axios.post(`${API}/vehicles/${vehicleId}/submit`, {}, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Submission failed' 
      };
    }
  }, [getAuthHeaders]);

  const getVehicles = useCallback(async (filters = {}) => {
    try {
      const params = new URLSearchParams(filters);
      const response = await axios.get(`${API}/vehicles?${params}`);
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to fetch vehicles' 
      };
    }
  }, []);

  const getVehicleDetail = useCallback(async (vehicleId) => {
    try {
      const response = await axios.get(`${API}/vehicles/${vehicleId}`, {
        headers: token ? getAuthHeaders() : {},
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Vehicle not found' 
      };
    }
  }, [token, getAuthHeaders]);

  const getMyListings = useCallback(async (status = null) => {
    try {
      const url = status ? `${API}/vehicles/my/listings?status=${status}` : `${API}/vehicles/my/listings`;
      const response = await axios.get(url, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to fetch listings' 
      };
    }
  }, [getAuthHeaders]);

  // ============= BIDDING =============
  const acceptTerms = useCallback(async (vehicleId) => {
    try {
      const response = await axios.post(`${API}/vehicles/${vehicleId}/accept-terms`, {}, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to accept terms' 
      };
    }
  }, [getAuthHeaders]);

  const payDeposit = useCallback(async (vehicleId) => {
    try {
      const response = await axios.post(`${API}/vehicle-bids/deposit?vehicle_id=${vehicleId}`, {}, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Deposit payment failed' 
      };
    }
  }, [getAuthHeaders]);

  const placeBid = useCallback(async (vehicleId, amount, maxBid = null) => {
    try {
      const response = await axios.post(`${API}/vehicle-bids`, {
        vehicle_id: vehicleId,
        amount,
        max_bid: maxBid,
      }, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Bid failed' 
      };
    }
  }, [getAuthHeaders]);

  const getMyBids = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/vehicle-bids/my`, {
        headers: getAuthHeaders(),
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Failed to fetch bids' 
      };
    }
  }, [getAuthHeaders]);

  // ============= PUBLIC ENDPOINTS =============
  const getSellerPublicProfile = useCallback(async (sellerId) => {
    try {
      const response = await axios.get(`${API}/vehicle-sellers/${sellerId}/public`);
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Seller not found' 
      };
    }
  }, []);

  const value = {
    sellerProfile,
    loading,
    setLoading,
    // VIN
    decodeVIN,
    // Seller
    registerAsSeller,
    getMySellerProfile,
    uploadSellerDocument,
    getSellerPublicProfile,
    // Vehicles
    createVehicleListing,
    uploadVehicleMedia,
    submitVehicleForApproval,
    getVehicles,
    getVehicleDetail,
    getMyListings,
    // Bidding
    acceptTerms,
    payDeposit,
    placeBid,
    getMyBids,
  };

  return (
    <VehicleAuctionContext.Provider value={value}>
      {children}
    </VehicleAuctionContext.Provider>
  );
};

export default VehicleAuctionContext;
