import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Activity, RefreshCw } from 'lucide-react';
import API_BASE from '../config';

const STATUS_STYLES = {
  success: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  timeout: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
  pending: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
};

const formatTime = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

export const SchedulerStatusCard = ({ token }) => {
  const [data, setData] = useState({ jobs: [], total_jobs: 0, scheduler_running: false });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await axios.get(`${API_BASE}/admin/scheduler/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data || { jobs: [], total_jobs: 0, scheduler_running: false });
    } catch (e) {
      // Surface to console for visibility but keep dashboard usable
      console.warn('[SchedulerStatus] fetch failed:', e?.response?.status || e?.message || e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // auto-refresh every 30s
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return (
    <div
      data-testid="scheduler-status-card"
      className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm"
    >
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-emerald-600" />
          <span>Scheduler Status</span>
          <span className="text-xs font-normal text-gray-500">
            ({data.total_jobs} jobs) · État du planificateur
          </span>
        </h3>
        <button
          type="button"
          data-testid="scheduler-status-refresh"
          onClick={fetchStatus}
          disabled={refreshing}
          className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : data.jobs.length === 0 ? (
        <p className="text-sm text-gray-500">No scheduled jobs reported yet.</p>
      ) : (
        <div className="max-h-80 overflow-y-auto pr-1">
          {data.jobs.map((job) => {
            const style = STATUS_STYLES[job.last_status] || STATUS_STYLES.pending;
            return (
              <div
                key={job.name}
                data-testid={`scheduler-job-${job.name}`}
                className="flex justify-between items-center py-2 border-b last:border-0 border-gray-100 dark:border-gray-700"
              >
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
                    {job.name}
                  </span>
                  <span className="text-xs text-gray-400">
                    last: {formatTime(job.last_run)} · next: {formatTime(job.next_run)}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${style}`}>
                    {job.last_status || 'pending'}
                  </span>
                  {typeof job.last_duration_ms === 'number' && (
                    <span className="text-xs text-gray-400">{job.last_duration_ms}ms</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SchedulerStatusCard;
