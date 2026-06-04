/**
 * AdminFacilities — iter178 (FIX 6) + iter212 Provincial Business Registration
 * =============================================================================
 * Lists all registered storage facilities with Verify/Suspend/Delete actions.
 * iter212: surfaces the provincial business-registration document with
 *   View → Verify/Reject buttons + structured-404 missing-file recovery modal.
 * Reuses existing /api/admin/storage-facilities endpoints.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Loader2, Building2, ShieldCheck, Ban, Trash2, FileText, XCircle, AlertTriangle, Mail, Eye,
} from 'lucide-react';

const API = API_BASE;

const STATUS_STYLES = {
  pending:  'bg-amber-100 text-amber-800',
  verified: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
  suspended:'bg-slate-200 text-slate-700',
  pending_verification: 'bg-amber-100 text-amber-800',
};

// Human-readable registration-type labels (mirror StorageFacilityRegister.js)
const REG_TYPE_LABEL = {
  federal_bn:        'Federal CRA BN',
  qc_neq:            'NEQ (QC)',
  on_ocn:            'OCN (ON)',
  bc_registry:       'BC Registry',
  ab_corporate:      'AB Corporate #',
  provincial_other:  'Provincial #',
  territorial_other: 'Territorial #',
};

// iter212 — token-bearing document opener (same pattern as PartnerManager)
// iter273 — Defensive 404 handling + facility context passthrough so the
// missing-doc modal can fire a "Request resubmission" call against the
// correct facility id without a second round trip.
const useDocOpener = (token, onMissing) => async (rawPath, facility) => {
  if (!rawPath) return;
  try {
    const abs = rawPath.startsWith('http') ? rawPath : `${process.env.REACT_APP_BACKEND_URL}${rawPath}`;
    const res = await fetch(abs, { headers: { Authorization: `Bearer ${token || ''}` } });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      return;
    }
    if (res.status === 404) {
      const data = await res.json().catch(() => ({}));
      const detail = (data && typeof data.detail === 'object') ? data.detail : {};
      // Trust the structured signal when present, but also treat ANY 404
      // on a storage_facilities path as a missing-file event so the admin
      // never sees a bare toast for this category.
      const isStorageFacilityDoc = (rawPath || '').includes('/storage_facilities/');
      if (detail.error_code === 'file_missing_on_disk' || isStorageFacilityDoc) {
        const fileName = (rawPath || '').split('/').pop() || '';
        onMissing({
          error_code:   detail.error_code || 'file_missing_on_disk',
          filename:     detail.filename || fileName,
          owner_email:  detail.owner_email || facility?.email,
          owner_user_id: detail.owner_user_id || facility?.owner_user_id,
          facility_id:  facility?.id,
          facility_name: facility?.company_name,
          message_en:   detail.message_en || (
            'This document is no longer available on the server. ' +
            'Files uploaded before the most recent redeployment may have been lost. ' +
            'Please ask the facility to re-upload their registration proof.'
          ),
          message_fr:   detail.message_fr || (
            'Ce document n\'est plus disponible sur le serveur. ' +
            'Veuillez demander à la facilité de téléverser à nouveau sa preuve d\'enregistrement.'
          ),
        });
        return;
      }
    }
    toast.error(`Failed to open document (HTTP ${res.status})`);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[facility-doc-open]', err);
    toast.error('Could not load document — network error.');
  }
};

const AdminFacilities = () => {
  const { token } = useAuth();
  const [facilities, setFacilities] = useState([]);
  const [filter, setFilter] = useState('');
  const [statusTab, setStatusTab] = useState('pending'); // 'pending' | 'all' | 'verified' | 'rejected'
  const [loading, setLoading] = useState(true);

  // iter212 — rejection modal + missing-doc modal
  const [rejectModal, setRejectModal] = useState(null); // facility being rejected
  const [rejectReason, setRejectReason] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [missingDocModal, setMissingDocModal] = useState(null);
  // iter273 — resubmission CTA in-flight flag
  const [requestingResubmit, setRequestingResubmit] = useState(false);

  const openDoc = useDocOpener(token, setMissingDocModal);

  const auth = { headers: { Authorization: `Bearer ${token}` } };

  // iter273 — Fires `POST /admin/storage-facilities/{id}/request-resubmission`
  // which emails the facility owner asking them to re-upload their
  // registration document. Idempotent on the backend.
  const requestResubmission = async () => {
    if (!missingDocModal?.facility_id) {
      toast.error('Missing facility id — refresh the page and try again.');
      return;
    }
    setRequestingResubmit(true);
    try {
      const r = await axios.post(
        `${API}/admin/storage-facilities/${missingDocModal.facility_id}/request-resubmission`,
        {},
        auth,
      );
      const sent = r?.data?.email_sent;
      toast.success(
        sent
          ? 'Resubmission request sent · Demande envoyée à la facilité'
          : 'Marked for resubmission (email pending) · Marqué pour re-soumission',
      );
      setMissingDocModal(null);
      loadFacilities();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message_en || 'Resubmission request failed');
    } finally {
      setRequestingResubmit(false);
    }
  };

  const loadFacilities = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/storage-facilities`, { headers: { Authorization: `Bearer ${token}` } });
      setFacilities(r.data?.facilities || r.data || []);
    } catch (e) {
      toast.error('Failed to load facilities · Échec');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadFacilities(); }, [loadFacilities]);

  const act = async (facility, action) => {
    if (action === 'delete' && !window.confirm('Delete this facility? · Supprimer cette facilité ?')) return;
    try {
      const endpoints = {
        verify: `/admin/storage-facilities/${facility.id}/verify`,
        suspend: `/admin/storage-facilities/${facility.id}/suspend`,
        delete: `/admin/storage-facilities/${facility.id}`,
        verifyReg: `/admin/storage-facilities/${facility.id}/verify-registration`,
      };
      if (action === 'delete') {
        await axios.delete(`${API}${endpoints.delete}`, auth);
      } else {
        await axios.post(`${API}${endpoints[action]}`, {}, auth);
      }
      toast.success(`Facility ${action}d · ${action}`);
      loadFacilities();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${action} failed`);
    }
  };

  const submitReject = async () => {
    if (!rejectModal) return;
    const reason = (rejectReason || '').trim();
    if (!reason) {
      toast.error('Please enter a rejection reason · Veuillez saisir un motif de rejet');
      return;
    }
    setRejecting(true);
    try {
      await axios.post(
        `${API}/admin/storage-facilities/${rejectModal.id}/reject-registration`,
        { reason },
        auth,
      );
      toast.success('Registration rejected · Enregistrement rejeté');
      setRejectModal(null);
      setRejectReason('');
      loadFacilities();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message_en || e?.response?.data?.detail || 'Reject failed');
    } finally {
      setRejecting(false);
    }
  };

  const filtered = facilities
    .filter((f) => {
      // iter212 — pending tab focuses on un-verified registrations
      if (statusTab === 'pending') return f.company_registration_verified === false;
      if (statusTab === 'verified') return f.status === 'verified';
      if (statusTab === 'rejected') return f.status === 'rejected';
      return true; // 'all'
    })
    .filter((f) =>
      !filter || (f.company_name || '').toLowerCase().includes(filter.toLowerCase()) ||
                 (f.city || '').toLowerCase().includes(filter.toLowerCase()) ||
                 (f.email || '').toLowerCase().includes(filter.toLowerCase()) ||
                 (f.company_registration_number || '').toLowerCase().includes(filter.toLowerCase())
    );

  const pendingCount = facilities.filter(f => f.company_registration_verified === false).length;

  return (
    <div data-testid="admin-facilities">
      <Card className="rounded-2xl">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-blue-600" />
              Storage Facilities · Facilités d'entreposage
              {pendingCount > 0 && (
                <Badge className="ml-2 bg-amber-100 text-amber-800" data-testid="pending-reg-badge">
                  {pendingCount} pending · en attente
                </Badge>
              )}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Verify business-registration documents, suspend, or delete facility operators
              · Vérifier les documents d'enregistrement, suspendre ou supprimer
            </p>
          </div>
          <Input
            placeholder="Search · Rechercher"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="max-w-xs"
            data-testid="admin-facilities-filter"
          />
        </CardHeader>
        <CardContent>
          {/* Status tabs */}
          <div className="flex gap-2 mb-3 flex-wrap" data-testid="facilities-tabs">
            {[
              { key: 'pending',  label_en: 'Pending Registration', label_fr: 'Inscription en attente' },
              { key: 'verified', label_en: 'Verified',              label_fr: 'Vérifiées' },
              { key: 'rejected', label_en: 'Rejected',              label_fr: 'Rejetées' },
              { key: 'all',      label_en: 'All',                   label_fr: 'Toutes' },
            ].map(tab => (
              <Button
                key={tab.key}
                size="sm"
                variant={statusTab === tab.key ? 'default' : 'outline'}
                onClick={() => setStatusTab(tab.key)}
                data-testid={`facilities-tab-${tab.key}`}
              >
                {tab.label_en} · {tab.label_fr}
                {tab.key === 'pending' && pendingCount > 0 && (
                  <span className="ml-1.5 rounded-full bg-amber-500 text-white text-[10px] px-1.5 py-0.5">
                    {pendingCount}
                  </span>
                )}
              </Button>
            ))}
          </div>

          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
          ) : filtered.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground" data-testid="facilities-empty">No facilities · Aucune facilité</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground border-b">
                  <tr>
                    <th className="text-left p-2">Company · Entreprise</th>
                    <th className="text-left p-2">Province</th>
                    <th className="text-left p-2">Registration · Enregistrement</th>
                    <th className="text-left p-2">Document</th>
                    <th className="text-left p-2">Status · Statut</th>
                    <th className="text-right p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => {
                    const regVerified = f.company_registration_verified === true;
                    const regRejected = !!f.company_registration_rejection_reason && !regVerified;
                    return (
                      <tr key={f.id} className="border-b hover:bg-slate-50" data-testid={`admin-facility-row-${f.id}`}>
                        <td className="p-2 align-top">
                          <div className="font-semibold">{f.company_name || '—'}</div>
                          <div className="text-[10px] text-muted-foreground">{f.email}</div>
                          <div className="text-[10px] text-muted-foreground">{f.contact_name} · {f.phone || ''}</div>
                          <div className="text-[10px] text-muted-foreground">{f.city}, {f.province}</div>
                        </td>
                        <td className="p-2 align-top text-xs">{f.province}</td>
                        <td className="p-2 align-top text-xs">
                          <div className="font-mono">{f.company_registration_number || '—'}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {REG_TYPE_LABEL[f.company_registration_type] || f.company_registration_type || '—'}
                          </div>
                          {f.company_registration_grandfathered && (
                            <Badge className="bg-slate-100 text-slate-700 text-[10px] mt-1">
                              Grandfathered · Existant
                            </Badge>
                          )}
                          {regRejected && (
                            <div className="text-[10px] text-rose-700 mt-1 line-clamp-2" title={f.company_registration_rejection_reason}>
                              ⚠️ {f.company_registration_rejection_reason}
                            </div>
                          )}
                        </td>
                        <td className="p-2 align-top">
                          {f.company_registration_document_url ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openDoc(f.company_registration_document_url, f)}
                              data-testid={`view-reg-doc-${f.id}`}
                              className="text-blue-700 border-blue-300"
                            >
                              <Eye className="h-3 w-3 mr-1" /> View · Voir
                            </Button>
                          ) : (
                            <span className="text-[10px] text-muted-foreground">No document</span>
                          )}
                        </td>
                        <td className="p-2 align-top">
                          <div className="flex flex-col gap-1">
                            <Badge className={STATUS_STYLES[f.status] || 'bg-slate-100'}>{f.status || 'unverified'}</Badge>
                            {regVerified ? (
                              <Badge className="bg-emerald-100 text-emerald-800 text-[10px]" data-testid={`reg-verified-badge-${f.id}`}>
                                <ShieldCheck className="h-3 w-3 mr-1 inline" /> Reg verified
                              </Badge>
                            ) : (
                              <Badge className="bg-amber-100 text-amber-800 text-[10px]" data-testid={`reg-pending-badge-${f.id}`}>
                                Reg pending
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="p-2 align-top text-right space-y-1">
                          {!regVerified && f.company_registration_document_url && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => act(f, 'verifyReg')}
                                className="border-emerald-300 text-emerald-700 w-full"
                                data-testid={`verify-reg-${f.id}`}
                              >
                                <ShieldCheck className="h-3 w-3 mr-1" />Verify · Vérifier
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => { setRejectModal(f); setRejectReason(''); }}
                                className="border-rose-300 text-rose-700 w-full"
                                data-testid={`reject-reg-${f.id}`}
                              >
                                <XCircle className="h-3 w-3 mr-1" />Reject · Rejeter
                              </Button>
                            </>
                          )}
                          {f.status !== 'verified' && (
                            <Button size="sm" variant="outline" onClick={() => act(f, 'verify')} className="border-emerald-300 text-emerald-700 w-full" data-testid={`facility-verify-${f.id}`}>
                              <ShieldCheck className="h-3 w-3 mr-1" />Approve · Approuver
                            </Button>
                          )}
                          {f.status !== 'suspended' && (
                            <Button size="sm" variant="outline" onClick={() => act(f, 'suspend')} className="border-amber-300 text-amber-700 w-full" data-testid={`facility-suspend-${f.id}`}>
                              <Ban className="h-3 w-3 mr-1" />Suspend · Suspendre
                            </Button>
                          )}
                          <Button size="sm" variant="outline" onClick={() => act(f, 'delete')} className="border-red-300 text-red-700 w-full" data-testid={`facility-delete-${f.id}`}>
                            <Trash2 className="h-3 w-3 mr-1" />Delete · Supprimer
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Reject-registration modal */}
      <Dialog open={!!rejectModal} onOpenChange={(o) => { if (!o) { setRejectModal(null); setRejectReason(''); } }}>
        <DialogContent data-testid="reject-reg-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-rose-600" />
              Reject business registration · Rejeter l'enregistrement
            </DialogTitle>
            <DialogDescription>
              <div className="text-sm">
                The facility will receive a bilingual email with this exact reason and a link to resubmit.
              </div>
              <div className="text-sm mt-1 text-muted-foreground">
                La facilité recevra un courriel bilingue avec ce motif exact et un lien pour soumettre à nouveau.
              </div>
            </DialogDescription>
          </DialogHeader>
          {rejectModal && (
            <div className="space-y-3">
              <div className="text-xs bg-slate-50 dark:bg-slate-800/40 p-2 rounded">
                <div><strong>{rejectModal.company_name}</strong></div>
                <div className="text-muted-foreground">{rejectModal.email}</div>
                <div className="font-mono text-[11px]">
                  {REG_TYPE_LABEL[rejectModal.company_registration_type] || rejectModal.company_registration_type}{' · '}
                  {rejectModal.company_registration_number}
                </div>
              </div>
              <div>
                <Label htmlFor="reject-reason">Rejection reason · Motif de rejet *</Label>
                <Textarea
                  id="reject-reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="e.g. The uploaded document is illegible. Please rescan and resubmit a clearer copy. · Ex. : le document est illisible…"
                  rows={4}
                  data-testid="reject-reason-input"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setRejectModal(null); setRejectReason(''); }}>
              Cancel · Annuler
            </Button>
            <Button
              onClick={submitReject}
              disabled={rejecting || !rejectReason.trim()}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="reject-reg-submit"
            >
              {rejecting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Mail className="h-4 w-4 mr-1" />}
              Reject & email facility · Rejeter et envoyer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Missing-document modal (file lost after redeploy) */}
      <Dialog open={!!missingDocModal} onOpenChange={(o) => { if (!o) setMissingDocModal(null); }}>
        <DialogContent data-testid="missing-doc-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              Document missing on disk · Document manquant
            </DialogTitle>
          </DialogHeader>
          {missingDocModal && (
            <div className="space-y-2 text-sm">
              <p>{missingDocModal.message_en}</p>
              <p className="text-muted-foreground">{missingDocModal.message_fr}</p>
              <div className="text-xs bg-slate-50 dark:bg-slate-800/40 p-2 rounded mt-3">
                <div><strong>Filename:</strong> {missingDocModal.filename}</div>
                <div><strong>Facility:</strong> {missingDocModal.facility_name || '—'}</div>
                <div><strong>Owner:</strong> {missingDocModal.owner_email || '—'}</div>
              </div>
            </div>
          )}
          <DialogFooter className="flex flex-col-reverse sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setMissingDocModal(null)}>
              Close · Fermer
            </Button>
            {missingDocModal?.facility_id && (
              <Button
                onClick={requestResubmission}
                disabled={requestingResubmit}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="request-resubmission-btn"
              >
                {requestingResubmit ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Mail className="h-4 w-4 mr-1" />}
                Request resubmission · Demander re-soumission
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminFacilities;
