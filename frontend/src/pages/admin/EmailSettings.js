import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  Mail, Shield, Send, CheckCircle2, XCircle, Loader2,
  Eye, EyeOff, Clock, AlertTriangle, Settings2
} from 'lucide-react';

const API = API_BASE;

const EmailSettings = () => {
  const { token } = useAuth();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const [apiKey, setApiKey] = useState('');
  const [fromEmail, setFromEmail] = useState('noreply@bidvex.com');
  const [fromName, setFromName] = useState('BidVex Partner Team');
  const [testRecipient, setTestRecipient] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/admin/email-settings`, { headers });
      setConfig(res.data);
      if (res.data.from_email) setFromEmail(res.data.from_email);
      if (res.data.from_name) setFromName(res.data.from_name);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleSave = async () => {
    if (!apiKey && !config?.configured) {
      toast.error('Please enter your SendGrid API key.');
      return;
    }
    setSaving(true);
    try {
      const payload = { from_email: fromEmail, from_name: fromName };
      if (apiKey) payload.api_key = apiKey;
      else if (config?.masked_key) {
        toast.error('Enter a new API key or leave the existing one unchanged.');
        setSaving(false);
        return;
      }
      await axios.post(`${API}/admin/email-settings`, payload, { headers });
      toast.success('SendGrid settings saved.');
      setApiKey('');
      fetchConfig();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save settings.');
    } finally { setSaving(false); }
  };

  const handleTest = async () => {
    if (!testRecipient) {
      toast.error('Enter a recipient email for the test.');
      return;
    }
    setTesting(true);
    try {
      const res = await axios.post(`${API}/admin/email-settings/test`, { recipient: testRecipient }, { headers });
      toast.success(res.data.message || 'Test email sent!');
      fetchConfig();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test email failed.');
    } finally { setTesting(false); }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>;
  }

  return (
    <div className="space-y-4" data-testid="email-settings-panel">
      {/* Status Banner */}
      <Card className={`border-2 ${config?.configured ? 'border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20' : 'border-amber-200 bg-amber-50/50 dark:bg-amber-950/20'}`}
        data-testid="email-status-banner">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            {config?.configured ? (
              <CheckCircle2 className="w-6 h-6 text-emerald-500 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-amber-500 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className="font-semibold text-sm">
                {config?.configured ? 'SendGrid Connected' : 'SendGrid Not Configured'}
              </p>
              <p className="text-xs text-slate-500">
                {config?.configured
                  ? `Key source: ${config.source}. Partner onboarding emails are active.`
                  : 'Paste your SendGrid API key below to enable automated partner emails.'}
              </p>
            </div>
            <Badge variant={config?.configured ? 'default' : 'secondary'} className="text-xs">
              {config?.configured ? 'Active' : 'Inactive'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Configuration Form */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-blue-500" /> SendGrid Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* API Key */}
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">API Key</label>
            <div className="relative">
              <Input
                type={showKey ? 'text' : 'password'}
                placeholder={config?.masked_key || 'SG.xxxxxxxxxx...'}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                className="pr-10 font-mono text-sm"
                data-testid="sendgrid-api-key-input"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Get your key at <a href="https://app.sendgrid.com/settings/api_keys" target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">SendGrid Dashboard</a>. Must start with "SG."
            </p>
          </div>

          {/* From Email */}
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Sender Email</label>
              <Input value={fromEmail} onChange={e => setFromEmail(e.target.value)}
                placeholder="noreply@bidvex.com" className="text-sm" data-testid="sendgrid-from-email" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 block mb-1">Sender Name</label>
              <Input value={fromName} onChange={e => setFromName(e.target.value)}
                placeholder="BidVex Partner Team" className="text-sm" data-testid="sendgrid-from-name" />
            </div>
          </div>

          <Button onClick={handleSave} disabled={saving} className="bg-blue-600 text-white hover:bg-blue-700"
            data-testid="save-email-settings-btn">
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
            Save Settings
          </Button>
        </CardContent>
      </Card>

      {/* Test Email */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Send className="w-4 h-4 text-cyan-500" /> Send Test Email
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">Recipient</label>
            <Input
              type="email"
              placeholder="your@email.com"
              value={testRecipient}
              onChange={e => setTestRecipient(e.target.value)}
              className="text-sm"
              data-testid="test-email-recipient"
            />
          </div>
          <Button
            onClick={handleTest}
            disabled={testing || !config?.configured}
            variant={config?.configured ? 'default' : 'secondary'}
            className={config?.configured ? 'bg-cyan-600 text-white hover:bg-cyan-700' : ''}
            data-testid="send-test-email-btn"
          >
            {testing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Mail className="w-4 h-4 mr-2" />}
            Send Test Email
          </Button>

          {/* Last Test Info */}
          {config?.last_test_at && (
            <div className="flex items-center gap-2 text-xs text-slate-500 mt-2" data-testid="last-test-info">
              <Clock className="w-3.5 h-3.5" />
              <span>Last test: {new Date(config.last_test_at).toLocaleString()}</span>
              {config.last_test_status === 'success' ? (
                <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Passed</Badge>
              ) : (
                <Badge className="bg-red-100 text-red-700 text-[10px]">Failed</Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* What Emails Are Sent */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Mail className="w-4 h-4 text-violet-500" /> Automated Partner Emails
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {[
              { trigger: 'Partner Application Received', to: 'Applicant + partners@bidvex.ca', status: config?.configured },
              { trigger: 'Partner Verified', to: 'Applicant', status: config?.configured },
              { trigger: 'Partner Rejected', to: 'Applicant', status: config?.configured },
            ].map((email, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div>
                  <p className="font-medium text-xs">{email.trigger}</p>
                  <p className="text-[11px] text-slate-400">To: {email.to}</p>
                </div>
                {email.status ? (
                  <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Active</Badge>
                ) : (
                  <Badge variant="secondary" className="text-[10px]">Pending Key</Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EmailSettings;
