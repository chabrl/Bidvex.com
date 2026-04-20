import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API = API_BASE;

const UnsubscribePage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid unsubscribe link.');
      return;
    }
    handleUnsubscribe();
  }, []);

  const handleUnsubscribe = async () => {
    try {
      const res = await axios.post(`${API}/marketing/unsubscribe`, { token });
      if (res.data.status === 'unsubscribed' || res.data.success) {
        setStatus('success');
        setMessage(res.data.message || 'You have been unsubscribed from marketing emails.');
      } else {
        setStatus('already');
        setMessage(res.data.message || 'You are already unsubscribed.');
      }
    } catch {
      setStatus('error');
      setMessage('Something went wrong. Please try again or contact support@bidvex.com.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center px-4" data-testid="unsubscribe-page">
      <div className="max-w-md w-full bg-white dark:bg-slate-900 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-800 p-8 text-center">
        <div className="mb-6">
          <img src="http://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png"
               alt="BidVex" className="h-10 mx-auto" />
        </div>

        {status === 'loading' && (
          <>
            <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-600 border-t-transparent mx-auto mb-4"></div>
            <p className="text-slate-600 dark:text-slate-400">Processing your request...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">✅</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Unsubscribed</h1>
            <p className="text-slate-600 dark:text-slate-400 text-sm">{message}</p>
            <p className="text-slate-500 dark:text-slate-500 text-xs mt-4">You will no longer receive marketing emails from BidVex. Transactional emails (bids, payments) will still be sent.</p>
          </>
        )}

        {status === 'already' && (
          <>
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">ℹ️</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Already Unsubscribed</h1>
            <p className="text-slate-600 dark:text-slate-400 text-sm">{message}</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">⚠️</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">Oops</h1>
            <p className="text-slate-600 dark:text-slate-400 text-sm">{message}</p>
            <a href="mailto:support@bidvex.com" className="inline-block mt-4 text-blue-600 hover:underline text-sm">Contact Support</a>
          </>
        )}

        <div className="mt-8 pt-4 border-t border-slate-200 dark:border-slate-800">
          <a href="https://www.bidvex.com" className="text-sm text-blue-600 hover:underline">Back to BidVex</a>
        </div>
      </div>
    </div>
  );
};

export default UnsubscribePage;
