/**
 * iter210 Step 5 — Admin Demo Accounts page.
 *
 * Renders a creation form + a live table of all demo accounts with
 * Extend / Convert / Delete actions. Status badge auto-colors based on
 * proximity to expiry.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2, Plus, Calendar, Copy, Trash2, ArrowUpRight, Clock } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';

const TYPE_LABELS = {
  vehicle_dealer:   { en: 'Vehicle Dealer',   fr: 'Marchand automobile' },
  partner:          { en: 'Partner',          fr: 'Partenaire' },
  storage_facility: { en: 'Storage Facility', fr: 'Établissement de stockage' },
  auctioneer:       { en: 'Auctioneer',       fr: 'Commissaire-priseur' },
};

const STATUS_BADGE = {
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  expiring_soon: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  expired: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
  converted: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

const STATUS_EMOJI = {
  active: '🟢',
  expiring_soon: '🟡',
  expired: '🔴',
  converted: '⚪',
};

const DemoAccountsPage = () => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    account_type: 'vehicle_dealer',
    company_name: '',
    contact_email: '',
    province: 'ON',
    duration_days: 14,
    notes: '',
  });
  const [lastCreatedPassword, setLastCreatedPassword] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/demo-accounts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error(isFr ? 'Échec de chargement' : 'Failed to load demo accounts');
    } finally {
      setLoading(false);
    }
  }, [token, isFr]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const createOne = async () => {
    setCreating(true);
    try {
      const r = await axios.post(`${API_BASE}/admin/demo-accounts`, form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      setLastCreatedPassword(r.data);
      toast.success(isFr ? `Compte démo créé pour ${r.data.email}` : `Demo account created for ${r.data.email}`);
      setForm({ ...form, company_name: '', contact_email: '', notes: '' });
      fetchAll();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : (isFr ? 'Échec' : 'Failed'));
    } finally {
      setCreating(false);
    }
  };

  const extend = async (id) => {
    try {
      await axios.post(`${API_BASE}/admin/demo-accounts/${id}/extend`, { additional_days: 14 }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(isFr ? '+14 jours' : '+14 days');
      fetchAll();
    } catch { toast.error(isFr ? 'Échec' : 'Failed'); }
  };

  const convert = async (id) => {
    if (!window.confirm(isFr ? 'Convertir ce compte démo en compte réel ?' : 'Convert this demo to a real account?')) return;
    try {
      await axios.post(`${API_BASE}/admin/demo-accounts/${id}/convert-to-real`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(isFr ? 'Converti — vérification requise' : 'Converted — verification required');
      fetchAll();
    } catch { toast.error(isFr ? 'Échec' : 'Failed'); }
  };

  const remove = async (id) => {
    if (!window.confirm(isFr ? 'Supprimer définitivement ?' : 'Permanently delete?')) return;
    try {
      await axios.delete(`${API_BASE}/admin/demo-accounts/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(isFr ? 'Supprimé' : 'Deleted');
      fetchAll();
    } catch { toast.error(isFr ? 'Échec' : 'Failed'); }
  };

  const copyPassword = (pwd) => {
    navigator.clipboard.writeText(pwd);
    toast.success(isFr ? 'Mot de passe copié' : 'Password copied');
  };

  return (
    <div className="space-y-6" data-testid="admin-demo-accounts-page">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          🎭 {isFr ? 'Comptes de démonstration' : 'Demo Accounts'}
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {isFr
            ? "Créez des comptes entièrement fonctionnels pour les démonstrations B2B. Aucun paiement réel n'est traité."
            : 'Create fully-functional accounts for B2B demos. No real payments are processed.'}
        </p>
      </header>

      {/* Last-created password (one-time display) */}
      {lastCreatedPassword && (
        <Card className="border-emerald-200 bg-emerald-50 dark:border-emerald-700/40 dark:bg-emerald-950/40">
          <CardContent className="pt-6">
            <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-200">
              {isFr ? '✅ Compte créé. Notez le mot de passe — il ne sera pas affiché à nouveau.' : '✅ Account created. Copy the temp password — it will not be shown again.'}
            </p>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-emerald-700 dark:text-emerald-400">Email:</span>{' '}
                <span className="font-mono">{lastCreatedPassword.email}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-emerald-700 dark:text-emerald-400">Password:</span>
                <span className="font-mono">{lastCreatedPassword.temp_password}</span>
                <Button size="sm" variant="ghost" onClick={() => copyPassword(lastCreatedPassword.temp_password)} data-testid="demo-copy-password">
                  <Copy className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
            <Button size="sm" variant="outline" className="mt-3" onClick={() => setLastCreatedPassword(null)}>
              {isFr ? 'Masquer' : 'Hide'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create form */}
      <Card data-testid="demo-create-form-card">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Plus className="w-4 h-4" /> {isFr ? 'Créer un compte démo' : 'Create a Demo Account'}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label className="text-xs">{isFr ? 'Type de compte' : 'Account Type'}</Label>
            <select
              value={form.account_type}
              onChange={e => setForm({ ...form, account_type: e.target.value })}
              data-testid="demo-form-account-type"
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 px-3 text-sm bg-white dark:bg-slate-900"
            >
              {Object.keys(TYPE_LABELS).map(t => (
                <option key={t} value={t}>{isFr ? TYPE_LABELS[t].fr : TYPE_LABELS[t].en}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs">{isFr ? "Nom de l'entreprise" : 'Company Name'}</Label>
            <Input value={form.company_name} onChange={e => setForm({ ...form, company_name: e.target.value })} data-testid="demo-form-company" />
          </div>
          <div>
            <Label className="text-xs">{isFr ? 'Courriel de contact' : 'Contact Email'}</Label>
            <Input type="email" value={form.contact_email} onChange={e => setForm({ ...form, contact_email: e.target.value })} data-testid="demo-form-email" />
          </div>
          <div>
            <Label className="text-xs">{isFr ? 'Province' : 'Province'}</Label>
            <Input value={form.province} onChange={e => setForm({ ...form, province: e.target.value })} placeholder="ON, QC, BC…" data-testid="demo-form-province" />
          </div>
          <div>
            <Label className="text-xs">{isFr ? 'Durée (jours)' : 'Demo Duration (days)'}</Label>
            <select
              value={form.duration_days}
              onChange={e => setForm({ ...form, duration_days: parseInt(e.target.value, 10) })}
              data-testid="demo-form-duration"
              className="w-full h-9 rounded-md border border-slate-300 dark:border-slate-700 px-3 text-sm bg-white dark:bg-slate-900"
            >
              <option value={7}>7 {isFr ? 'jours' : 'days'}</option>
              <option value={14}>14 {isFr ? 'jours' : 'days'}</option>
              <option value={30}>30 {isFr ? 'jours' : 'days'}</option>
              <option value={60}>60 {isFr ? 'jours' : 'days'}</option>
              <option value={90}>90 {isFr ? 'jours' : 'days'}</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <Label className="text-xs">{isFr ? 'Notes internes' : 'Internal Notes'}</Label>
            <Input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder={isFr ? 'À qui s’adresse cette démo ?' : 'Who is this demo for?'} data-testid="demo-form-notes" />
          </div>
          <div className="md:col-span-2 flex justify-end">
            <Button
              onClick={createOne}
              disabled={creating || !form.company_name || !form.contact_email}
              data-testid="demo-create-submit-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {creating ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {isFr ? 'Création…' : 'Creating…'}</>
              ) : (
                <><Plus className="w-4 h-4 mr-2" /> {isFr ? 'Créer le compte démo' : 'Create demo account'}</>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{isFr ? 'Comptes existants' : 'Existing Demo Accounts'}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="demo-table-loading">
              <Loader2 className="w-4 h-4 animate-spin" /> {isFr ? 'Chargement…' : 'Loading…'}
            </div>
          ) : items.length === 0 ? (
            <p className="text-sm text-slate-500" data-testid="demo-table-empty">
              {isFr ? 'Aucun compte démo. Créez le premier ci-dessus.' : 'No demo accounts yet. Create the first one above.'}
            </p>
          ) : (
            <div className="overflow-x-auto" data-testid="demo-table">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase text-slate-500 border-b border-slate-200 dark:border-slate-700/40">
                    <th className="text-left py-2 pr-3">Company</th>
                    <th className="text-left py-2 pr-3">Type</th>
                    <th className="text-left py-2 pr-3">Email</th>
                    <th className="text-left py-2 pr-3">Province</th>
                    <th className="text-left py-2 pr-3">Created</th>
                    <th className="text-left py-2 pr-3">Expires</th>
                    <th className="text-left py-2 pr-3">Status</th>
                    <th className="text-right py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id} className="border-b border-slate-100 dark:border-slate-800" data-testid={`demo-row-${row.id}`}>
                      <td className="py-2 pr-3 font-semibold text-slate-900 dark:text-white">{row.company_name}</td>
                      <td className="py-2 pr-3">{isFr ? TYPE_LABELS[row.account_type]?.fr : TYPE_LABELS[row.account_type]?.en}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{row.email}</td>
                      <td className="py-2 pr-3">{row.province}</td>
                      <td className="py-2 pr-3 text-xs text-slate-500">{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td>
                      <td className="py-2 pr-3 text-xs text-slate-500">{row.expires_at ? new Date(row.expires_at).toLocaleDateString() : '—'}</td>
                      <td className="py-2 pr-3">
                        <Badge className={STATUS_BADGE[row.status] || STATUS_BADGE.active}>
                          {STATUS_EMOJI[row.status] || '🟢'} {row.status}
                        </Badge>
                      </td>
                      <td className="py-2 text-right space-x-1">
                        <Button size="sm" variant="outline" onClick={() => extend(row.id)} data-testid={`demo-extend-${row.id}`}>
                          <Clock className="w-3.5 h-3.5 mr-1" /> +14d
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => convert(row.id)} data-testid={`demo-convert-${row.id}`}>
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => remove(row.id)} data-testid={`demo-delete-${row.id}`}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default DemoAccountsPage;
