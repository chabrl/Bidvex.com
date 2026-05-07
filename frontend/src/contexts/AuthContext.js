import API_BASE from '../config';
import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import i18n from '../i18n';

const AuthContext = createContext(null);

// ─── iter189 Bug 5: Global 401→refresh interceptor ───
// Installed once at module load. On any 401 with "token_expired" response,
// swap a fresh access token via /auth/refresh and retry the original request.
// Only logout if the refresh itself fails.
let _isRefreshing = false;
let _pendingQueue = [];
const _flushQueue = (err, newToken) => {
  _pendingQueue.forEach(({ resolve, reject }) => {
    if (err) reject(err);
    else resolve(newToken);
  });
  _pendingQueue = [];
};

axios.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const alreadyRetried = original?._retry;
    const url = original?.url || '';
    // Never recurse on the refresh call itself, nor on login/register/logout which return
    // their own 401s for credential failures (not token expiry).
    const isAuthExempt = /\/auth\/(refresh|login|register|logout|google)/.test(url);
    // Prefer the backend's "token_expired" marker, but fall back to any 401 with a refresh
    // token present — matches the iter180 bilingual error response shape.
    const detailStr = typeof detail === 'string' ? detail : (detail?.error || detail?.code || '');
    const isTokenExpired = status === 401 && (
      detailStr === 'token_expired' || detailStr === 'Token expired' || detailStr === 'expired'
      || !detailStr // generic 401 with empty detail → attempt refresh
    );
    if (!isTokenExpired || alreadyRetried || isAuthExempt) {
      return Promise.reject(error);
    }

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return Promise.reject(error);

    original._retry = true;

    if (_isRefreshing) {
      // Queue up concurrent requests until the in-flight refresh resolves
      return new Promise((resolve, reject) => {
        _pendingQueue.push({
          resolve: (tok) => {
            original.headers = original.headers || {};
            original.headers.Authorization = `Bearer ${tok}`;
            resolve(axios(original));
          },
          reject,
        });
      });
    }

    _isRefreshing = true;
    try {
      const resp = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refreshToken });
      const newAccess = resp.data?.access_token;
      const newRefresh = resp.data?.refresh_token;
      if (!newAccess) throw new Error('No access token in refresh response');
      localStorage.setItem('token', newAccess);
      if (newRefresh) localStorage.setItem('refresh_token', newRefresh);
      axios.defaults.headers.common['Authorization'] = `Bearer ${newAccess}`;
      _flushQueue(null, newAccess);
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${newAccess}`;
      return axios(original);
    } catch (refreshErr) {
      _flushQueue(refreshErr, null);
      // Refresh failed → full logout
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      delete axios.defaults.headers.common['Authorization'];
      // Let any top-level auth provider clear user state (non-fatal)
      try { window.dispatchEvent(new CustomEvent('bidvex:auth:logout', { detail: { reason: 'refresh_failed' } })); } catch (_) {}
      return Promise.reject(error);
    } finally {
      _isRefreshing = false;
    }
  }
);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));

  const API = API_BASE;

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
      // Only logout on 401 (invalid/expired token). Network errors or 500s should NOT force logout.
      if (error.response?.status === 401) {
        logout();
      }
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    console.log('Attempting login for:', email);
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const { access_token, refresh_token, user: userData } = response.data;
      console.log('Login successful. User:', userData);
      console.log('Token received:', access_token ? 'yes' : 'no');
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('token', access_token);
      if (refresh_token) localStorage.setItem('refresh_token', refresh_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Sync language preference with i18next
      if (userData.preferred_language) {
        i18n.changeLanguage(userData.preferred_language);
      }
      
      return userData;
    } catch (error) {
      // Check if this is a password reset required error
      if (error.response?.status === 403) {
        const detail = error.response?.data?.detail;
        if (detail && typeof detail === 'object' && detail.code === 'PASSWORD_RESET_REQUIRED') {
          // Throw a special error that the UI can handle
          const resetError = new Error('PASSWORD_RESET_REQUIRED');
          resetError.resetToken = detail.reset_token;
          resetError.userId = detail.user_id;
          resetError.message = detail.message;
          throw resetError;
        }
      }
      // Re-throw other errors
      throw error;
    }
  };

  const register = async (userData) => {
    const response = await axios.post(`${API}/auth/register`, userData);
    const { access_token, refresh_token, user: newUser } = response.data;
    setToken(access_token);
    setUser(newUser);
    localStorage.setItem('token', access_token);
    if (refresh_token) localStorage.setItem('refresh_token', refresh_token);
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

  // Direct Google OAuth — accepts a JWT minted by the backend's
  // /api/auth/google/callback handler, persists it, and hydrates the user.
  const setUserFromToken = async (jwt) => {
    if (!jwt) throw new Error('No token provided');
    setToken(jwt);
    localStorage.setItem('token', jwt);
    axios.defaults.headers.common['Authorization'] = `Bearer ${jwt}`;
    const me = await axios.get(`${API}/auth/me`);
    setUser(me.data);
    return me.data;
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
    localStorage.removeItem('refresh_token');
    delete axios.defaults.headers.common['Authorization'];
  };

  // iter189 Bug 5: Listen for interceptor-initiated logout (refresh failed)
  useEffect(() => {
    const handler = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener('bidvex:auth:logout', handler);
    return () => window.removeEventListener('bidvex:auth:logout', handler);
  }, []);

  // Refresh user data (used after phone verification)
  const refreshUser = async () => {
    if (token) {
      try {
        const response = await axios.get(`${API}/auth/me`);
        setUser(response.data);
        return response.data;
      } catch (error) {
        console.error('Failed to refresh user:', error);
        throw error;
      }
    }
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
      
      // Check if currency is locked
      if (error.response?.status === 403 && error.response?.data?.detail?.error === 'currency_locked') {
        // Return the error details for UI to handle
        throw {
          currencyLocked: true,
          message: error.response.data.detail.message,
          enforcedCurrency: error.response.data.detail.enforced_currency,
          appealLink: error.response.data.detail.appeal_link
        };
      }
      
      throw error;
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, processGoogleSession, setUserFromToken, updateUserPreferences, refreshUser, token }}>
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
