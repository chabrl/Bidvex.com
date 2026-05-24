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
import { Handshake, ShieldCheck, Clock, XCircle, AlertTriangle, CreditCard, Eye, FileText, ExternalLink, Paperclip } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AdminBrokerAuditDrawer from '../../components/admin/AdminBrokerAuditDrawer';

const SUBTABS = [
  { id: 'pending_review', en: 'Pending',   fr: 'En attente',  count_key: 'pending_review', icon: Clock,        color: 'bg-amber-100 text-amber-800' },
  { id: 'approved',       en: 'Approved',  fr: 'Approuvés',   count_key: 'approved',       icon: ShieldCheck,  color: 'bg-emerald-100 text-emerald-800' },
  { id: 'rejected',       en: 'Rejected',  fr: 'Rejetés',     count_key: 'rejected',       icon: XCircle,      color: 'bg-rose-100 text-rose-800' },
  { id: 'suspended',      en: 'Suspended', fr: 'Suspendus',   count_key: 'suspended',      icon: AlertTriangle, color: 'bg-orange-100 text-orange-800' },
];

export default function AdminBrokersPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const navigate = useNavigate();
  const [subtab, setSubtab] = useState('pending_review');
  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [auditBroker, setAuditBroker] = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = useCallback(async (status) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/brokers?status=${status}`, {
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
      const path = `/admin/brokers/${brokerId}/${action}`;
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
      <header className="mb-6 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="admin-brokers-title">
            <Handshake className="h-7 w-7" />
            {lang === 'fr' ? 'Gestion des courtiers' : 'Broker Management'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {lang === 'fr'
              ? 'Vérifiez et gérez les demandes de courtiers commerciaux.'
              : 'Review and manage commercial broker applications.'}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate('/admin/subscriptions')}
          data-testid="goto-subscriptions-btn"
        >
          <CreditCard className="h-4 w-4 mr-2" />
          {lang === 'fr' ? 'Gérer les abonnements' : 'Manage Subscriptions'}
        </Button>
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

                  {/* iter227 Fix #4 — Admin attachment / compliance docs viewer */}
                  <BrokerDocuments broker={b} lang={lang} />
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setAuditBroker(b)}
                    data-testid={`admin-broker-audit-${b.id}`}
                    title={lang === 'fr' ? 'Inspecter ce courtier' : 'Inspect this broker'}
                  >
                    <Eye className="h-3.5 w-3.5 mr-1" />
                    {lang === 'fr' ? 'Audit' : 'Audit'}
                  </Button>
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

      {/* iter226 Task 2 — Admin Broker Audit Drawer */}
      <AdminBrokerAuditDrawer
        open={!!auditBroker}
        broker={auditBroker}
        lang={lang}
        onClose={() => setAuditBroker(null)}
      />
    </div>
  );
}

// ── iter227 Fix #4 — Compliance Documents block for a broker row ──────
function BrokerDocuments({ broker, lang }) {
  const docs = [];
  if (broker.license_document_url) {
    docs.push({ kind: 'license', url: broker.license_document_url,
                en: 'Broker / Dealer Licence', fr: 'Licence courtier / concessionnaire' });
  }
  if (broker.registration_document_url) {
    docs.push({ kind: 'registration', url: broker.registration_document_url,
                en: 'Corporate Registration', fr: 'Inscription corporative' });
  }
  (broker.additional_documents || []).forEach((url, i) => {
    docs.push({ kind: `extra-${i}`, url,
                en: `Additional Document ${i + 1}`, fr: `Document supplémentaire ${i + 1}` });
  });

  // Provincial license numbers — surfaced inline so admin sees them before approving
  const provLabels = [];
  if (broker.qc_anq_number)   provLabels.push(['ANQ',   broker.qc_anq_number]);
  if (broker.qc_opc_number)   provLabels.push(['OPC',   broker.qc_opc_number]);
  if (broker.on_omvic_number) provLabels.push(['OMVIC', broker.on_omvic_number]);
  if (broker.bc_vsa_number)   provLabels.push(['VSA',   broker.bc_vsa_number]);
  if (broker.ab_amvic_number) provLabels.push(['AMVIC', broker.ab_amvic_number]);

  if (docs.length === 0 && provLabels.length === 0) {
    return (
      <div className="mt-2 text-xs text-rose-600 flex items-center gap-1.5" data-testid={`broker-no-docs-${broker.id}`}>
        <AlertTriangle className="w-3.5 h-3.5" />
        {lang === 'fr' ? 'Aucun document compliance téléversé.' : 'No compliance documents uploaded.'}
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-3 space-y-2" data-testid={`broker-docs-${broker.id}`}>
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
        <Paperclip className="w-3.5 h-3.5" />
        {lang === 'fr' ? 'Documents de conformité' : 'Compliance Documents'}
        <span className="ml-auto text-[10px] font-normal text-slate-400">
          {docs.length} {lang === 'fr' ? 'fichier(s)' : 'file(s)'}
        </span>
      </div>

      {provLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pb-1" data-testid={`broker-provincial-${broker.id}`}>
          {provLabels.map(([k, v]) => (
            <Badge key={k} className="bg-blue-100 text-blue-800 font-mono text-[10px]">{k}: {v}</Badge>
          ))}
        </div>
      )}

      {docs.length === 0 ? (
        <p className="text-[11px] text-amber-700">
          {lang === 'fr' ? 'Aucun fichier téléversé pour ce courtier.' : 'No files uploaded for this broker.'}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
          {docs.map((d) => {
            const isImage = /\.(png|jpe?g|webp|gif|heic|heif)(\?.*)?$/i.test(d.url);
            return (
              <a
                key={d.kind}
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-2 px-2.5 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-xs hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition"
                data-testid={`broker-doc-link-${broker.id}-${d.kind}`}
                title={lang === 'fr' ? 'Ouvrir dans un nouvel onglet' : 'Open in new tab'}
              >
                <FileText className="w-3.5 h-3.5 flex-shrink-0 text-blue-600" />
                <span className="flex-1 min-w-0 truncate font-medium">
                  {lang === 'fr' ? d.fr : d.en}
                </span>
                {isImage && (
                  <span className="text-[9px] uppercase font-bold text-emerald-700 bg-emerald-100 px-1 rounded">
                    IMG
                  </span>
                )}
                <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-blue-600" />
              </a>
            );
          })}
        </div>
      )}
      <p className="text-[10px] text-slate-500 italic">
        {lang === 'fr'
          ? 'Vérifiez chaque document avant d\'approuver. Les liens s\'ouvrent dans un nouvel onglet.'
          : 'Verify each document before approval. Links open in a new tab.'}
      </p>
    </div>
  );
}
