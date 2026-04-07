import React, { useState, useEffect, useCallback } from 'react';
import API_BASE from '../../config';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import {
  Activity, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  Shield, Wifi, Database, CreditCard, Mail, Clock, Server,
  ChevronDown, ChevronUp, Loader2,
} from 'lucide-react';

const API = API_BASE;

const STATUS_COLORS = {
  operational: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  critical: 'bg-red-500',
  healthy: 'bg-emerald-500',
  down: 'bg-red-500',
  not_configured: 'bg-slate-400',
};

const STATUS_TEXT = {
  operational: 'Operational',
  degraded: 'Degraded',
  critical: 'Critical',
  healthy: 'Healthy',
  down: 'Down',
  not_configured: 'Not Configured',
};

function StatusDot({ status }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${STATUS_COLORS[status] || 'bg-slate-400'} animate-pulse`}
      data-testid={`status-dot-${status}`}
    />
  );
}

function MetricCard({ title, value, subtitle, icon: Icon, trend, testId }) {
  return (
    <Card className="border-slate-200" data-testid={testId}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
            <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          <div className="p-2.5 rounded-lg bg-slate-100">
            <Icon className="h-5 w-5 text-slate-600" />
          </div>
        </div>
        {trend !== undefined && (
          <p className={`text-xs mt-2 font-medium ${trend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {trend >= 0 ? '+' : ''}{trend}% vs last period
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function AlertRow({ alert }) {
  const isError = alert.severity === 'error' || alert.severity === 'critical';
  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg border ${isError ? 'border-red-200 bg-red-50' : 'border-amber-200 bg-amber-50'}`}
      data-testid="alert-row"
    >
      {isError ? (
        <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
      ) : (
        <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 truncate">{alert.message}</p>
        <div className="flex items-center gap-2 mt-1">
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {alert.event_type}
          </Badge>
          <span className="text-[10px] text-slate-500">
            {new Date(alert.created_at).toLocaleString()}
          </span>
        </div>
      </div>
      {alert.resolved && (
        <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Resolved</Badge>
      )}
    </div>
  );
}

function WebhookRow({ event }) {
  const isFailed = event.status === 'failed';
  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-lg border ${isFailed ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-white'}`}
      data-testid="webhook-row"
    >
      {isFailed ? (
        <XCircle className="h-4 w-4 text-red-500 shrink-0" />
      ) : (
        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 uppercase">
            {event.provider}
          </Badge>
          <span className="text-sm font-medium text-slate-700 truncate">{event.event_type}</span>
        </div>
        <span className="text-[10px] text-slate-500">
          {new Date(event.created_at).toLocaleString()}
        </span>
      </div>
      {event.details?.error && (
        <span className="text-[10px] text-red-600 max-w-[200px] truncate">{event.details.error}</span>
      )}
    </div>
  );
}

export default function SystemMonitoringDashboard() {
  const { token } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [healthCheck, setHealthCheck] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const [showAllWebhooks, setShowAllWebhooks] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchDashboard = useCallback(async () => {
    try {
      const [dashRes, healthRes] = await Promise.all([
        axios.get(`${API}/monitoring/dashboard`, { headers }),
        axios.get(`${API}/monitoring/health-check`, { headers }),
      ]);
      setDashboard(dashRes.data);
      setHealthCheck(healthRes.data);
    } catch (err) {
      console.error('Monitoring fetch error:', err);
      toast.error('Failed to load monitoring data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboard();
  };

  const handleResolve = async (eventType) => {
    try {
      await axios.post(`${API}/monitoring/resolve/${eventType}`, {}, { headers });
      toast.success(`Resolved all ${eventType} alerts`);
      fetchDashboard();
    } catch {
      toast.error('Failed to resolve alerts');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const d = dashboard || {};
  const h = healthCheck || {};
  const alerts = d.recent_alerts || [];
  const webhookFailures = d.recent_webhook_failures || [];
  const recent500s = d.recent_500s || [];
  const visibleAlerts = showAllAlerts ? alerts : alerts.slice(0, 5);
  const visibleWebhooks = showAllWebhooks ? webhookFailures : webhookFailures.slice(0, 5);

  return (
    <div className="space-y-6" data-testid="system-monitoring-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-900">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">System Monitoring</h2>
            <p className="text-xs text-slate-500">Real-time platform health & alerts</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <StatusDot status={d.system_status || 'operational'} />
            <span className="text-sm font-semibold text-slate-700">
              {STATUS_TEXT[d.system_status] || 'Unknown'}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            data-testid="refresh-monitoring-btn"
          >
            <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Errors (24h)"
          value={d.errors?.last_24h ?? 0}
          subtitle={`${d.errors?.unresolved ?? 0} unresolved`}
          icon={AlertTriangle}
          testId="metric-errors-24h"
        />
        <MetricCard
          title="Webhook Success"
          value={`${d.webhooks?.success_rate ?? 100}%`}
          subtitle={`${d.webhooks?.total_24h ?? 0} total (24h)`}
          icon={Wifi}
          testId="metric-webhook-success"
        />
        <MetricCard
          title="Stripe Failures"
          value={d.webhooks?.stripe_failures_24h ?? 0}
          subtitle="Last 24 hours"
          icon={CreditCard}
          testId="metric-stripe-failures"
        />
        <MetricCard
          title="500 Errors"
          value={recent500s.length}
          subtitle="Recent occurrences"
          icon={Server}
          testId="metric-500-errors"
        />
      </div>

      {/* Service Health */}
      <Card data-testid="service-health-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Service Health
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* MongoDB */}
            <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border">
              <Database className="h-5 w-5 text-slate-600" />
              <div>
                <p className="text-sm font-medium">MongoDB</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <StatusDot status={h.checks?.mongodb?.status || 'healthy'} />
                  <span className="text-xs text-slate-600">
                    {STATUS_TEXT[h.checks?.mongodb?.status] || 'Checking...'}
                  </span>
                </div>
              </div>
            </div>
            {/* Stripe */}
            <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border">
              <CreditCard className="h-5 w-5 text-slate-600" />
              <div>
                <p className="text-sm font-medium">Stripe</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <StatusDot status={h.checks?.stripe?.status || 'healthy'} />
                  <span className="text-xs text-slate-600">
                    {STATUS_TEXT[h.checks?.stripe?.status] || 'Checking...'}
                  </span>
                </div>
              </div>
            </div>
            {/* Collections */}
            <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border">
              <Server className="h-5 w-5 text-slate-600" />
              <div>
                <p className="text-sm font-medium">Data Store</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <StatusDot status={h.checks?.collections ? 'healthy' : 'degraded'} />
                  <span className="text-xs text-slate-600">
                    {h.checks?.collections?.users ?? '?'} users, {h.checks?.collections?.listings ?? '?'} listings
                  </span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Two-Column: Alerts + Webhook Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Alerts */}
        <Card data-testid="recent-alerts-card">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Recent Alerts
                {(d.errors?.unresolved ?? 0) > 0 && (
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0 ml-1">
                    {d.errors.unresolved}
                  </Badge>
                )}
              </CardTitle>
              {alerts.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  onClick={() => handleResolve('http_500')}
                  data-testid="resolve-500-btn"
                >
                  Resolve 500s
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <CheckCircle2 className="h-8 w-8 mx-auto mb-2" />
                <p className="text-sm">No recent alerts</p>
              </div>
            ) : (
              <div className="space-y-2">
                {visibleAlerts.map((a, i) => (
                  <AlertRow key={i} alert={a} />
                ))}
                {alerts.length > 5 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs"
                    onClick={() => setShowAllAlerts(!showAllAlerts)}
                  >
                    {showAllAlerts ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
                    {showAllAlerts ? 'Show less' : `Show all ${alerts.length}`}
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Webhook Log */}
        <Card data-testid="webhook-log-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Wifi className="h-4 w-4" />
              Webhook Failures
              {(d.webhooks?.failures_24h ?? 0) > 0 && (
                <Badge variant="destructive" className="text-[10px] px-1.5 py-0 ml-1">
                  {d.webhooks.failures_24h}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {webhookFailures.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <CheckCircle2 className="h-8 w-8 mx-auto mb-2" />
                <p className="text-sm">No webhook failures</p>
              </div>
            ) : (
              <div className="space-y-2">
                {visibleWebhooks.map((w, i) => (
                  <WebhookRow key={i} event={w} />
                ))}
                {webhookFailures.length > 5 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs"
                    onClick={() => setShowAllWebhooks(!showAllWebhooks)}
                  >
                    {showAllWebhooks ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
                    {showAllWebhooks ? 'Show less' : `Show all ${webhookFailures.length}`}
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Footer */}
      <p className="text-[10px] text-slate-400 text-center">
        Auto-refreshes every 30s &middot; Last updated: {d.generated_at ? new Date(d.generated_at).toLocaleTimeString() : '—'}
      </p>
    </div>
  );
}
