/**
 * iter217 Phase 5 Hotfix v5b — Admin Broker Management page.
 * Sub-tabs: Pending | Approved | Rejected | Suspended
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Handshake, ShieldCheck, Clock, XCircle, AlertTriangle } from 'lucide-react';

const SUBTABS = [
  { id: 'pending_review', en: 'Pending',   fr: 'En attente',  count_key: 'pending_review', icon: Clock,        color: 'bg-amber-100 text-amber-800' },
  { id: 'approved',       en: 'Approved',  fr: 'Approuvés',   count_key: 'approved',       icon: ShieldCheck,  color: 'bg-emerald-100 text-emerald-800' },
  { id: 'rejected',       en: 'Rejected',  fr: 'Rejetés',     count_key: 'rejected',       icon: XCircle,      color: 'bg-rose-100 text-rose-800' },
  { id: 'suspended',      en: 'Suspended', fr: 'Suspendus',   count_key: 'suspended',      icon: AlertTriangle, color: 'bg-orange-100 text-orange-800' },
];

export default function AdminBrokersPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const [subtab, setSubtab] = useState('pending_review');
  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(true);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = useCallback(async (status) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/api/admin/brokers?status=${status}`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setBrokers(r.data?.data || []);
    } catch {
      setBrokers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(subtab); }, [load, subtab]);

  const handleAction = async (brokerId, action, reason) => {
    try {
      const path = `/api/admin/brokers/${brokerId}/${action}`;
      const body = (action === 'reject' || action === 'suspend') && reason ? { reason } : {};
      await axios.patch(`${API_BASE}${path}`, body, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      load(subtab);
    } catch (e) {
      alert(e?.response?.data?.detail?.error || 'Action failed');
    }
  };

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <header className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="admin-brokers-title">
          <Handshake className="h-7 w-7" />
          {lang === 'fr' ? 'Gestion des courtiers' : 'Broker Management'}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {lang === 'fr'
            ? 'Vérifiez et gérez les demandes de courtiers commerciaux.'
            : 'Review and manage commercial broker applications.'}
        </p>
      </header>

      <div className="flex gap-2 mb-4 flex-wrap" data-testid="admin-brokers-subtabs">
        {SUBTABS.map(s => {
          const Icon = s.icon;
          return (
            <button
              key={s.id}
              onClick={() => setSubtab(s.id)}
              className={`px-4 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition ${
                subtab === s.id
                  ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white shadow'
                  : 'bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
              data-testid={`admin-brokers-subtab-${s.id}`}
            >
              <Icon className="h-4 w-4" />
              {lang === 'fr' ? s.fr : s.en}
            </button>
          );
        })}
      </div>

      {loading && <p className="text-center text-slate-500 py-8">Loading…</p>}

      {!loading && brokers.length === 0 && (
        <Card><CardContent className="p-8 text-center text-slate-500">
          {lang === 'fr' ? 'Aucun courtier dans cette catégorie.' : 'No brokers in this category.'}
        </CardContent></Card>
      )}

      <div className="space-y-3">
        {brokers.map((b) => (
          <Card key={b.id} data-testid={`admin-broker-row-${b.id}`}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex-1 min-w-[260px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-lg">{b.legal_business_name}</h3>
                    <Badge>{b.operating_province}</Badge>
                    <Badge variant="outline">{b.regulatory_body}</Badge>
                  </div>
                  <div className="text-sm text-slate-600 dark:text-slate-300 mt-1">
                    {lang === 'fr' ? 'Licence' : 'License'}: <code>{b.broker_license_number}</code> · {lang === 'fr' ? 'Inscription' : 'Reg #'}: <code>{b.corporate_registration_number}</code>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {lang === 'fr' ? 'Utilisateur' : 'User'}: {b.user_email} ({b.user_name})
                  </div>
                  <div className="text-sm mt-2">
                    {b.fee_structure?.type === 'fixed'
                      ? `Fixed: $${Number(b.fee_structure.fixed_amount_cad).toFixed(0)} per deal`
                      : `${(Number(b.fee_structure?.percentage_rate || 0) * 100).toFixed(2)}% of hammer`}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {subtab === 'pending_review' && (
                    <>
                      <Button size="sm" onClick={() => handleAction(b.id, 'approve')} data-testid={`admin-broker-approve-${b.id}`}>
                        ✓ {lang === 'fr' ? 'Approuver' : 'Approve'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => {
                        const r = window.prompt(lang === 'fr' ? 'Raison du rejet:' : 'Rejection reason:');
                        if (r) handleAction(b.id, 'reject', r);
                      }} data-testid={`admin-broker-reject-${b.id}`}>
                        ✗ {lang === 'fr' ? 'Rejeter' : 'Reject'}
                      </Button>
                    </>
                  )}
                  {subtab === 'approved' && (
                    <Button size="sm" variant="outline" onClick={() => {
                      const r = window.prompt(lang === 'fr' ? 'Raison de la suspension:' : 'Suspension reason:');
                      if (r) handleAction(b.id, 'suspend', r);
                    }} data-testid={`admin-broker-suspend-${b.id}`}>
                      ⚠ {lang === 'fr' ? 'Suspendre' : 'Suspend'}
                    </Button>
                  )}
                  {(subtab === 'rejected' || subtab === 'suspended') && b.verification_status !== 'approved' && (
                    <Button size="sm" onClick={() => handleAction(b.id, 'approve')} data-testid={`admin-broker-reapprove-${b.id}`}>
                      ↻ {lang === 'fr' ? 'Ré-approuver' : 'Re-approve'}
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
