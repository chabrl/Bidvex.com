/**
 * iter259 — Partner Trial Offers admin subsection.
 *
 * Lives inside the Admin Promotions Engine, immediately ABOVE the
 * "All Promotions" table. Renders three pre-built trial offer cards
 * (Dealer / Broker / Storage) plus an "Active Partner Trials" table
 * with Extend +30d and Revoke actions.
 *
 * Backed by:
 *   POST   /api/promotions/partner-trial            (admin guarded)
 *   GET    /api/admin/partner-trials                (list)
 *   PATCH  /api/admin/partner-trials/{id}/extend    (+30 days)
 *   DELETE /api/admin/partner-trials/{id}           (revoke)
 *
 * The public landing page (`/promotions/partners`) was removed in
 * iter259 — trials are now activated exclusively by BidVex staff,
 * one user_id at a time, from this admin surface.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import { Car, Award, Warehouse, Play, RefreshCw, Clock, X } from 'lucide-react';
import API_BASE from '../../config';

const TRIAL_OFFERS = [
  {
    key: 'dealer',
    label: 'Vehicle Dealers & Brokers',
    icon: Car,
    duration: 30,
    accent: 'border-blue-200 bg-blue-50/60',
    bullets: [
      '3 Featured Listings',
      'Verified Dealer Badge',
      'Real-time Analytics',
      'Geo-targeted Reach',
    ],
  },
  {
    key: 'broker',
    label: 'Licensed Broker Partner Program',
    icon: Award,
    duration: 60,
    accent: 'border-amber-200 bg-amber-50/60',
    bullets: [
      'Unlimited Listings',
      'Verified Broker Badge',
      'Public Broker Profile',
      'Client Referral Tools + Early Access',
    ],
  },
  {
    key: 'storage',
    label: 'Storage Facilities',
    icon: Warehouse,
    duration: 45,
    accent: 'border-emerald-200 bg-emerald-50/60',
    bullets: [
      '5 Featured Storage Listings',
      'Facility Profile Page',
      'Tenant Notification Tools',
      'Compliant Abandoned-Property Workflow',
    ],
  },
];

const STATUS_BADGE = {
  active:   'bg-emerald-100 text-emerald-800',
  expired:  'bg-slate-100 text-slate-600',
  revoked:  'bg-rose-100 text-rose-800',
};

const PartnerTrialsAdminSection = ({ token }) => {
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }),
    [token],
  );

  const [activateModal, setActivateModal] = useState({ open: false, partnerType: null });
  // iter274 — Modal supports two activation modes:
  //   • "existing"  → search for a registered user, activate trial in-place (legacy)
  //   • "coupon"    → mint a BVX-TRIAL-* coupon for an unregistered partner,
  //                    optionally fire the bilingual invite email
  const [activateMode, setActivateMode] = useState('existing');
  const [searchQuery, setSearchQuery] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [form, setForm] = useState({
    company_name: '',
    licence_number: '',
    province: 'QC',
    phone: '',
  });
  // iter274 — coupon-mode fields + last minted coupon shown back to admin
  const [couponForm, setCouponForm] = useState({
    recipient_email: '',
    recipient_name: '',
    company_name: '',
    send_invite_email: true,
    note: '',
  });
  const [lastMintedCoupon, setLastMintedCoupon] = useState(null);
  const [busy, setBusy] = useState(false);

  const [trials, setTrials] = useState([]);
  const [trialsLoading, setTrialsLoading] = useState(false);
  const [trialPage, setTrialPage] = useState(1);
  const [trialTotal, setTrialTotal] = useState(0);

  const fetchTrials = useCallback(async () => {
    setTrialsLoading(true);
    try {
      const r = await axios.get(
        `${API_BASE}/admin/partner-trials`,
        { headers, params: { page: trialPage, limit: 20 } },
      );
      setTrials(Array.isArray(r.data?.items) ? r.data.items : []);
      setTrialTotal(Number(r.data?.total || 0));
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load partner trials');
    } finally {
      setTrialsLoading(false);
    }
  }, [headers, trialPage]);

  useEffect(() => { fetchTrials(); }, [fetchTrials]);

  // Lightweight user search (admin scope) — re-uses the admin users list.
  const runUserSearch = useCallback(async (q) => {
    if (!q || q.trim().length < 2) { setUserResults([]); return; }
    try {
      const r = await axios.get(
        `${API_BASE}/admin/users`,
        { headers, params: { search: q.trim(), limit: 8 } },
      );
      const items = Array.isArray(r.data?.users)
        ? r.data.users
        : Array.isArray(r.data) ? r.data : [];
      setUserResults(items.slice(0, 8));
    } catch {
      setUserResults([]);
    }
  }, [headers]);

  const openActivate = (partnerType) => {
    setActivateModal({ open: true, partnerType });
    setActivateMode('existing');
    setSearchQuery('');
    setUserResults([]);
    setSelectedUser(null);
    setForm({ company_name: '', licence_number: '', province: 'QC', phone: '' });
    setCouponForm({
      recipient_email: '',
      recipient_name: '',
      company_name: '',
      send_invite_email: true,
      note: '',
    });
    setLastMintedCoupon(null);
  };

  // iter274 — Mint a tracking-friendly trial coupon for an unregistered
  // partner via POST /api/admin/promotions/activate-trial. On success we
  // pin the coupon to local state so the admin can copy the signup URL
  // / code straight from the modal.
  const mintCoupon = async () => {
    if (!activateModal.partnerType) return;
    if (couponForm.recipient_email && !/^[^@]+@[^@]+\.[^@]+$/.test(couponForm.recipient_email)) {
      toast.error('Recipient email looks invalid');
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(
        `${API_BASE}/admin/promotions/activate-trial`,
        {
          partner_type:      activateModal.partnerType,
          recipient_email:   couponForm.recipient_email.trim() || null,
          recipient_name:    couponForm.recipient_name.trim() || null,
          company_name:      couponForm.company_name.trim() || null,
          send_invite_email: !!couponForm.send_invite_email,
          note:              couponForm.note.trim() || null,
        },
        { headers },
      );
      const data = r?.data || {};
      const coupon = data.coupon || {};
      setLastMintedCoupon(coupon);
      toast.success(
        data.deduped
          ? `Existing coupon reused: ${coupon.code}`
          : `Coupon minted: ${coupon.code}${data.email_sent ? ' (invite emailed)' : ''}`,
      );
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message_en || e?.response?.data?.detail || 'Failed to mint coupon');
    } finally {
      setBusy(false);
    }
  };

  // iter274 — Copy helper for the coupon-display panel.
  const copyToClipboard = (text) => {
    try {
      navigator.clipboard.writeText(text || '');
      toast.success('Copied to clipboard');
    } catch {
      toast.error('Copy failed — select the text manually');
    }
  };

  const submitActivate = async () => {
    if (!selectedUser) { toast.error('Pick a user'); return; }
    if (!form.company_name.trim() || form.company_name.trim().length < 2) {
      toast.error('Company name is required (min 2 chars)');
      return;
    }
    if (activateModal.partnerType === 'broker' && !form.licence_number.trim()) {
      toast.error('Licence number is required for brokers');
      return;
    }
    if (!form.phone.trim()) { toast.error('Phone is required'); return; }
    setBusy(true);
    try {
      await axios.post(
        `${API_BASE}/promotions/partner-trial`,
        {
          user_id: selectedUser.id,
          partner_type: activateModal.partnerType,
          company_name: form.company_name.trim(),
          licence_number: form.licence_number.trim() || null,
          province: (form.province || 'QC').toUpperCase(),
          phone: form.phone.trim(),
        },
        { headers },
      );
      toast.success(`Trial activated for ${selectedUser.email}`);
      setActivateModal({ open: false, partnerType: null });
      fetchTrials();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to activate trial');
    } finally {
      setBusy(false);
    }
  };

  const extendTrial = async (id) => {
    try {
      await axios.patch(`${API_BASE}/admin/partner-trials/${id}/extend`, {}, { headers });
      toast.success('Trial extended +30 days');
      fetchTrials();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to extend trial');
    }
  };

  const revokeTrial = async (id) => {
    if (!window.confirm('Revoke this partner trial? The user will be emailed.')) return;
    try {
      await axios.delete(`${API_BASE}/admin/partner-trials/${id}`, { headers });
      toast.success('Trial revoked');
      fetchTrials();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to revoke trial');
    }
  };

  const offer = TRIAL_OFFERS.find((o) => o.key === activateModal.partnerType);
  const trialExpiry = offer ? new Date(Date.now() + offer.duration * 86400_000) : null;

  return (
    <div className="space-y-4" data-testid="partner-trials-admin-section">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            🎯 Partner Trial Offers
          </CardTitle>
          <p className="text-xs text-slate-500">
            Activate a free trial for a specific user. The public landing
            page was removed in iter259 — trials are admin-only.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="partner-trial-cards">
            {TRIAL_OFFERS.map((o) => {
              const Icon = o.icon;
              return (
                <div
                  key={o.key}
                  className={`rounded-lg border-2 p-4 ${o.accent}`}
                  data-testid={`partner-trial-card-${o.key}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="h-5 w-5 text-slate-700" />
                    <h4 className="font-bold text-slate-900 text-sm">{o.label}</h4>
                  </div>
                  <Badge className="bg-white border border-slate-300 text-slate-700 mb-3">
                    FREE {o.duration}-Day Trial
                  </Badge>
                  <ul className="text-xs text-slate-700 space-y-1 mb-3">
                    {o.bullets.map((b, i) => (
                      <li key={i}>• {b}</li>
                    ))}
                  </ul>
                  <Button
                    size="sm"
                    className="w-full font-bold"
                    style={{ backgroundColor: '#0055FF', color: 'white' }}
                    onClick={() => openActivate(o.key)}
                    data-testid={`activate-trial-${o.key}`}
                  >
                    <Play className="h-3.5 w-3.5 mr-1.5" />
                    Activate for a User
                  </Button>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm">
            Active Partner Trials ({trialTotal})
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchTrials}
            data-testid="refresh-partner-trials"
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          {trialsLoading ? (
            <p className="text-xs text-slate-500 text-center py-4">Loading…</p>
          ) : trials.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-4">No partner trials yet.</p>
          ) : (
            <table className="w-full text-sm" data-testid="partner-trials-table">
              <thead>
                <tr className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <th className="text-left p-2">User</th>
                  <th className="text-left">Type</th>
                  <th className="text-left">Company</th>
                  <th className="text-left">Trial Expires</th>
                  <th className="text-center">Status</th>
                  <th className="text-right pr-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {trials.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-slate-100"
                    data-testid={`partner-trial-row-${t.id}`}
                  >
                    <td className="p-2">
                      <div className="font-semibold text-slate-900">{t.user_name || '—'}</div>
                      <div className="text-xs text-slate-500">{t.user_email || t.user_id}</div>
                    </td>
                    <td className="text-xs font-bold uppercase">{t.partner_type}</td>
                    <td className="text-xs">{t.company_name}</td>
                    <td className="text-xs">
                      {(t.trial_expires_at || '').slice(0, 10)}
                    </td>
                    <td className="text-center">
                      <Badge className={STATUS_BADGE[t.status] || 'bg-slate-100 text-slate-700'}>
                        {t.status}
                      </Badge>
                    </td>
                    <td className="text-right pr-3 space-x-1">
                      {t.status === 'active' && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => extendTrial(t.id)}
                            data-testid={`extend-trial-${t.id}`}
                          >
                            <Clock className="h-3 w-3 mr-1" />
                            Extend 30d
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => revokeTrial(t.id)}
                            data-testid={`revoke-trial-${t.id}`}
                          >
                            <X className="h-3 w-3 mr-1" />
                            Revoke
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Activate modal */}
      <Dialog
        open={activateModal.open}
        onOpenChange={(o) => !o && setActivateModal({ open: false, partnerType: null })}
      >
        <DialogContent data-testid="activate-trial-modal" className="max-w-md">
          <DialogHeader>
            <DialogTitle className="capitalize">
              Activate {activateModal.partnerType} Trial
            </DialogTitle>
          </DialogHeader>

          {/* iter274 — Mode toggle */}
          <div
            className="flex gap-2 mb-2"
            role="tablist"
            data-testid="activate-mode-toggle"
          >
            <Button
              size="sm"
              variant={activateMode === 'existing' ? 'default' : 'outline'}
              onClick={() => setActivateMode('existing')}
              data-testid="activate-mode-existing"
              style={activateMode === 'existing' ? { backgroundColor: '#0055FF', color: 'white' } : {}}
            >
              Existing User
            </Button>
            <Button
              size="sm"
              variant={activateMode === 'coupon' ? 'default' : 'outline'}
              onClick={() => setActivateMode('coupon')}
              data-testid="activate-mode-coupon"
              style={activateMode === 'coupon' ? { backgroundColor: '#0055FF', color: 'white' } : {}}
            >
              🎟️ Generate Coupon
            </Button>
          </div>

          {/* ── EXISTING USER MODE (legacy iter259 flow) ── */}
          {activateMode === 'existing' && (
          <div className="space-y-3" data-testid="activate-existing-mode">
            <div>
              <Label className="text-xs">Search User *</Label>
              <Input
                value={searchQuery}
                placeholder="email or name…"
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  runUserSearch(e.target.value);
                  setSelectedUser(null);
                }}
                data-testid="activate-trial-user-search"
              />
              {userResults.length > 0 && !selectedUser && (
                <ul className="border border-slate-200 rounded-md mt-1 max-h-32 overflow-y-auto bg-white">
                  {userResults.map((u) => (
                    <li
                      key={u.id}
                      className="px-2 py-1 text-sm hover:bg-slate-100 cursor-pointer"
                      onClick={() => {
                        setSelectedUser(u);
                        setSearchQuery(u.email);
                        setUserResults([]);
                      }}
                      data-testid={`activate-trial-pick-user-${u.id}`}
                    >
                      <span className="font-semibold">{u.name || u.email}</span>
                      <span className="text-xs text-slate-500 ml-2">{u.email}</span>
                    </li>
                  ))}
                </ul>
              )}
              {selectedUser && (
                <p className="text-xs text-emerald-700 mt-1">
                  Selected: <strong>{selectedUser.email}</strong>
                </p>
              )}
            </div>
            <div>
              <Label className="text-xs">Company Name *</Label>
              <Input
                value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                data-testid="activate-trial-company"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Province *</Label>
                <Input
                  value={form.province}
                  onChange={(e) => setForm({ ...form, province: e.target.value })}
                  data-testid="activate-trial-province"
                  maxLength={4}
                />
              </div>
              <div>
                <Label className="text-xs">Phone *</Label>
                <Input
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  data-testid="activate-trial-phone"
                />
              </div>
            </div>
            {activateModal.partnerType === 'broker' && (
              <div>
                <Label className="text-xs">Licence # (required for broker) *</Label>
                <Input
                  value={form.licence_number}
                  onChange={(e) => setForm({ ...form, licence_number: e.target.value })}
                  data-testid="activate-trial-licence"
                />
              </div>
            )}
            {trialExpiry && (
              <p className="text-xs text-slate-500">
                Trial will expire: <strong>{trialExpiry.toISOString().slice(0, 10)}</strong>
              </p>
            )}
          </div>
          )}

          {/* ── COUPON MODE (iter274) ── */}
          {activateMode === 'coupon' && (
          <div className="space-y-3" data-testid="activate-coupon-mode">
            <p className="text-xs text-slate-500">
              Mint a one-shot <code>BVX-TRIAL-XXXXXXXX</code> code. Share
              the generated link with an unregistered partner — they sign
              up via the link and the {offer?.duration || 30}-day annual
              fee waiver activates automatically.
            </p>
            <div>
              <Label className="text-xs">Recipient Email <span className="text-slate-400">(optional)</span></Label>
              <Input
                type="email"
                value={couponForm.recipient_email}
                onChange={(e) => setCouponForm({ ...couponForm, recipient_email: e.target.value })}
                placeholder="auctioneer@example.com"
                data-testid="coupon-recipient-email"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Recipient Name</Label>
                <Input
                  value={couponForm.recipient_name}
                  onChange={(e) => setCouponForm({ ...couponForm, recipient_name: e.target.value })}
                  data-testid="coupon-recipient-name"
                />
              </div>
              <div>
                <Label className="text-xs">Company Name</Label>
                <Input
                  value={couponForm.company_name}
                  onChange={(e) => setCouponForm({ ...couponForm, company_name: e.target.value })}
                  data-testid="coupon-company-name"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Internal Note</Label>
              <Input
                value={couponForm.note}
                onChange={(e) => setCouponForm({ ...couponForm, note: e.target.value })}
                placeholder="Why this coupon?"
                data-testid="coupon-note"
              />
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={couponForm.send_invite_email}
                onChange={(e) => setCouponForm({ ...couponForm, send_invite_email: e.target.checked })}
                data-testid="coupon-send-invite-toggle"
              />
              Email the invite link to the recipient now
            </label>

            {/* Minted coupon panel */}
            {lastMintedCoupon && (
              <div
                className="rounded-md border border-emerald-200 bg-emerald-50 p-3 space-y-2"
                data-testid="coupon-result-panel"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-800">Coupon ready</span>
                  <Badge className="bg-emerald-200 text-emerald-900">
                    {lastMintedCoupon.duration_days}d {lastMintedCoupon.partner_type}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  <code
                    className="text-sm font-mono bg-white border border-emerald-300 px-2 py-1 rounded flex-1"
                    data-testid="coupon-result-code"
                  >
                    {lastMintedCoupon.code}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(lastMintedCoupon.code)}
                    data-testid="coupon-copy-code"
                  >
                    Copy
                  </Button>
                </div>
                <div className="flex items-center gap-1">
                  <code
                    className="text-[10px] font-mono bg-white border border-emerald-300 px-2 py-1 rounded flex-1 truncate"
                    title={lastMintedCoupon.signup_url}
                    data-testid="coupon-result-signup-url"
                  >
                    {lastMintedCoupon.signup_url}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(lastMintedCoupon.signup_url)}
                    data-testid="coupon-copy-url"
                  >
                    Copy
                  </Button>
                </div>
              </div>
            )}
          </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setActivateModal({ open: false, partnerType: null })}
              data-testid="activate-trial-cancel"
            >
              Close
            </Button>
            {activateMode === 'existing' ? (
              <Button
                onClick={submitActivate}
                disabled={busy || !selectedUser}
                style={{ backgroundColor: '#0055FF', color: 'white' }}
                data-testid="activate-trial-submit"
              >
                {busy ? 'Activating…' : '✅ Activate Trial & Notify User'}
              </Button>
            ) : (
              <Button
                onClick={mintCoupon}
                disabled={busy}
                style={{ backgroundColor: '#0055FF', color: 'white' }}
                data-testid="coupon-mint-submit"
              >
                {busy ? 'Minting…' : '🎟️ Generate Coupon'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PartnerTrialsAdminSection;
