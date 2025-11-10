import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import i18n from '../i18n';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));

  const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      console.log('Fetching user with token:', token ? 'exists' : 'missing');
      const response = await axios.get(`${API}/auth/me`);
      console.log('User fetched successfully:', response.data);
      setUser(response.data);
      
      // Sync language preference with i18next
      if (response.data.preferred_language) {
        i18n.changeLanguage(response.data.preferred_language);
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
      console.error('Error response:', error.response?.data);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    console.log('Attempting login for:', email);
    const response = await axios.post(`${API}/auth/login`, { email, password });
    const { access_token, user: userData } = response.data;
    console.log('Login successful. User:', userData);
    console.log('Token received:', access_token ? 'yes' : 'no');
    setToken(access_token);
    setUser(userData);
    localStorage.setItem('token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    
    // Sync language preference with i18next
    if (userData.preferred_language) {
      i18n.changeLanguage(userData.preferred_language);
    }
    
    return userData;
  };

  const register = async (userData) => {
    const response = await axios.post(`${API}/auth/register`, userData);
    const { access_token, user: newUser } = response.data;
    setToken(access_token);
    setUser(newUser);
    localStorage.setItem('token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    return newUser;
  };

  const processGoogleSession = async (sessionId) => {
    const response = await axios.post(`${API}/auth/session`, { session_id: sessionId });
    const { session_token } = response.data;
    setToken(session_token);
    localStorage.setItem('token', session_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${session_token}`;
    await fetchUser();
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`);
    } catch (error) {
      console.error('Logout error:', error);
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  const updateUserPreferences = async (preferences) => {
    try {
      const response = await axios.put(`${API}/users/me`, preferences);
      
      // Update local user state
      const updatedResponse = await axios.get(`${API}/auth/me`);
      setUser(updatedResponse.data);
      
      // Sync language with i18next if changed
      if (preferences.preferred_language) {
        i18n.changeLanguage(preferences.preferred_language);
      }
      
      return updatedResponse.data;
    } catch (error) {
      console.error('Failed to update preferences:', error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, processGoogleSession, updateUserPreferences, token }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
