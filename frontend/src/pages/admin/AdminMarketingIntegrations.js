/**
 * AdminMarketingIntegrations — iter178 (FIX 7)
 * =============================================
 * Save Facebook Pixel, Google Tag Manager, Google Ads IDs to
 * site_config.marketing. Values are loaded by MarketingPixelLoader
 * on app boot and injected into the document head.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Megaphone, Save } from 'lucide-react';

const API = API_BASE;

const AdminMarketingIntegrations = () => {
  const { token } = useAuth();
  const [form, setForm] = useState({ fb_pixel_id: '', gtm_id: '', google_ads_id: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/site-config`, { headers: { Authorization: `Bearer ${token}` } });
      const m = r.data?.marketing || {};
      setForm({
        fb_pixel_id: m.fb_pixel_id || '',
        gtm_id: m.gtm_id || '',
        google_ads_id: m.google_ads_id || '',
      });
    } catch (e) {
      toast.error('Failed to load · Échec');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/site-config/marketing`, form, auth);
      toast.success('Marketing settings saved · Paramètres enregistrés');
    } catch (e) {
      toast.error('Save failed · Échec');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="py-12 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  }

  return (
    <div data-testid="admin-marketing-integrations" className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="h-6 w-6 text-blue-600" />
          Marketing Integrations · Intégrations marketing
        </h2>
        <p className="text-sm text-muted-foreground">Configure tracking pixels and analytics — injected automatically on app boot.</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Google Analytics & Ads</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label>GTM Container ID</Label>
            <Input
              placeholder="GTM-XXXXXXX"
              value={form.gtm_id}
              onChange={(e) => setForm((f) => ({ ...f, gtm_id: e.target.value }))}
              data-testid="gtm-id-input"
            />
          </div>
          <div>
            <Label>Google Ads Conversion ID</Label>
            <Input
              placeholder="AW-XXXXXXXXXX"
              value={form.google_ads_id}
              onChange={(e) => setForm((f) => ({ ...f, google_ads_id: e.target.value }))}
              data-testid="google-ads-id-input"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Facebook / Meta Pixel</CardTitle></CardHeader>
        <CardContent>
          <Label>Pixel ID</Label>
          <Input
            placeholder="123456789012345"
            value={form.fb_pixel_id}
            onChange={(e) => setForm((f) => ({ ...f, fb_pixel_id: e.target.value }))}
            data-testid="fb-pixel-id-input"
          />
          <p className="text-xs text-muted-foreground mt-2">
            Tracked events: ViewContent (on listing view), AddToCart (on bid), Purchase (on win).
          </p>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="marketing-save-btn">
          {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
          Save · Enregistrer
        </Button>
      </div>
    </div>
  );
};

export default AdminMarketingIntegrations;
