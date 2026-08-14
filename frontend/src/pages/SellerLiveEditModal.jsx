/**
 * iter483.3 — Seller Live Edit Modal (responsive · bid-locks · Request Center)
 * ============================================================================
 *
 * Restricted, non-financial edit surface for an active auction owned
 * by the current seller.  Sections:
 *
 *   Info       · Title + Description  (locked at auction level once bids arrive)
 *   Media      · Auction hero images  (S3 uploader; stays editable after bids)
 *   Lots       · Per-lot cards with own uploader (each lot fully locked after
 *                its first bid)
 *   Schedule   · Preview + Pickup     (locked at auction level after bids)
 *   Shipping   · Shipping settings    (locked at auction level after bids)
 *   Add Lot    · Draft-lot submission (multi-lot auctions only)
 *   Requests   · UNIFIED Auction Request Center — submit + track
 *                { end_time · reserve_price · edit } requests
 *   History    · Immutable edited_history log
 *
 * Backend contract (routes/live_edit.py + routes/auction_requests.py):
 *   GET   /api/auctions/{id}/edit-state
 *   GET   /api/auctions/{id}/edited-history
 *   PATCH /api/auctions/{id}/live-edit         {field, value}
 *   POST  /api/auctions/{id}/lots              {lot: {...}}
 *   GET   /api/auctions/{id}/requests
 *   POST  /api/auctions/{id}/requests          {request_type, target, payload, reason}
 *
 * Responsive rules:
 *   Mobile   (<640px) — full-screen sheet · horizontal tab pills · sticky Save
 *   Tablet   (640–1024px) — 90vw, max 720px · horizontal tab pills
 *   Desktop  (>1024px) — max 860px centered · horizontal tab pills
 */
import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogAction,
  AlertDialogCancel,
} from '../components/ui/alert-dialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Loader2, Save, Calendar, Truck, Plus, Clock, History,
  Check, X, Upload, Lock, Package, MessageSquare, DollarSign,
  FileText,
} from 'lucide-react';
import API_BASE from '../config';

const API = API_BASE;

// ─────────────────────────────────────────────────────────────────────
//  Bilingual labels
// ─────────────────────────────────────────────────────────────────────

function useBilingual() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  return {
    fr,
    L: fr ? FR : EN,
  };
}

const EN = {
  title:              'Edit Auction',
  info:               'Info',
  media:              'Media',
  lots:               'Lots',
  schedule:           'Schedule & Pickup',
  shipping:           'Shipping',
  addLot:             'Add Lot',
  requests:           'Requests',
  history:            'History',
  saveInfo:           'Save info',
  saveSchedule:       'Save schedule',
  saveShipping:       'Save shipping',
  savedOk:            'Saved',
  saveFailed:         'Save failed',
  fieldTitle:         'Title',
  fieldDescription:   'Description',
  previewDate:        'Preview date',
  previewTime:        'Preview time',
  pickupLocation:     'Pickup location',
  pickupWindowStart:  'Pickup window start',
  pickupWindowEnd:    'Pickup window end',
  pickupInstructions: 'Pickup instructions',
  shippingAvailable:  'Shipping available',
  shippingNotes:      'Shipping notes',
  shippingEstimate:   'Estimated cost (info only)',
  shippingEstimateHelp:'This is an estimate. No Stripe payment is charged.',
  carrier:            'Carrier',
  addImage:           'Add image',
  uploadHint:         'Drag & drop or click to upload your images',
  uploadingCount:     'Uploading',
  uploadAccepted:     'JPG · PNG · WEBP · 10 MB max per file',
  uploadRejectedType: 'Unsupported file type',
  uploadRejectedSize: 'File too large (max 10 MB)',
  uploadFailed:       'Upload failed',
  currentImages:      'Current images',
  removeOwnOnly:      'You can only remove images you added.',
  newLotTitle:        'New lot title',
  newLotDescription:  'Description',
  newLotQuantity:     'Quantity',
  newLotStartPrice:   'Starting price',
  newLotCategory:     'Category',
  newLotCondition:    'Condition',
  submitNewLot:       'Submit for review',
  newLotPending:      'New lot added — pending admin review.',
  endTimeCurrent:     'Current end time',
  endTimeRequestBtn:  'Request end-time change',
  endTimeRequestedNew:'Requested new end time',
  endTimeReason:      'Reason (minimum 20 characters)',
  endTimeSubmit:      'Send request',
  endTimePending:     'Request pending',
  endTimeApproved:    'Request approved',
  endTimeDenied:      'Request denied',
  adminNoteLabel:     'Admin note',
  historyEmpty:       'No changes recorded for this auction.',
  close:              'Close',
  // iter483.3
  lockedByBids:       'Locked — bids placed',
  auctionLocked:      'This auction has active bids. To request a change, use the Request Center below.',
  submitEditRequest:  'Submit Edit Request',
  requestCenter:      'Auction Request Center',
  requestType:        'Request type',
  reqEndTime:         'End-time change',
  reqReservePrice:    'Reserve price',
  reqEdit:            'Edit locked field',
  reqTarget:          'Target',
  reqTargetAuction:   'Whole auction',
  reqTargetLot:       'Lot',
  reqReservePriceInput:'Requested reserve price ($)',
  reqEditField:       'Field',
  reqEditNewValue:    'Requested new value',
  reqReason:          'Reason (min 20 chars)',
  reqSubmit:          'Submit request',
  reqSubmitted:       'Request submitted',
  reqYourRequests:    'Your requests',
  reqNone:            'No requests yet.',
  reqStatusPending:   'Pending',
  reqStatusApproved:  'Approved',
  reqStatusDenied:    'Denied',
  reqDuplicate:       'A pending request of this type already exists',
  unsavedTitle:       'Discard unsaved changes?',
  unsavedDesc:        'You have unsaved edits in this section. Leave anyway?',
  discard:            'Discard',
  keepEditing:        'Keep editing',
  lotBids:            'bids',
  lotLockedMsg:       'This lot is locked because it has received bids. You can no longer edit it directly.',
  lotSectionTitle:    'Lots in this auction',
  lotEmpty:           'This auction has no lots to edit.',
  lotDropHint:        'Drag & drop or click to upload photos for this lot',
};

const FR = {
  title:              'Modifier l\u2019enchère',
  info:               'Informations',
  media:              'Médias',
  lots:               'Lots',
  schedule:           'Calendrier & Ramassage',
  shipping:           'Expédition',
  addLot:             'Ajouter un lot',
  requests:           'Demandes',
  history:            'Historique',
  saveInfo:           'Enregistrer les informations',
  saveSchedule:       'Enregistrer le calendrier',
  saveShipping:       'Enregistrer l\u2019expédition',
  savedOk:            'Enregistré',
  saveFailed:         'Échec de l\u2019enregistrement',
  fieldTitle:         'Titre',
  fieldDescription:   'Description',
  previewDate:        'Date d\u2019aperçu',
  previewTime:        'Heure d\u2019aperçu',
  pickupLocation:     'Lieu de ramassage',
  pickupWindowStart:  'Début de la fenêtre',
  pickupWindowEnd:    'Fin de la fenêtre',
  pickupInstructions: 'Instructions de ramassage',
  shippingAvailable:  'Expédition disponible',
  shippingNotes:      'Notes d\u2019expédition',
  shippingEstimate:   'Coût estimé (info seulement)',
  shippingEstimateHelp:'Ceci est une estimation. Aucun paiement Stripe n\u2019est prélevé.',
  carrier:            'Transporteur',
  addImage:           'Ajouter des images',
  uploadHint:         'Glissez-déposez ou cliquez pour téléverser vos images',
  uploadingCount:     'Téléversement en cours',
  uploadAccepted:     'JPG · PNG · WEBP · 10 Mo max par fichier',
  uploadRejectedType: 'Format non supporté',
  uploadRejectedSize: 'Fichier trop volumineux (max 10 Mo)',
  uploadFailed:       'Échec du téléversement',
  currentImages:      'Images actuelles',
  removeOwnOnly:      'Vous ne pouvez retirer que les images que vous avez ajoutées.',
  newLotTitle:        'Titre du nouveau lot',
  newLotDescription:  'Description',
  newLotQuantity:     'Quantité',
  newLotStartPrice:   'Mise de départ',
  newLotCategory:     'Catégorie',
  newLotCondition:    'État',
  submitNewLot:       'Soumettre pour approbation',
  newLotPending:      'Nouveau lot ajouté — en attente de révision admin.',
  endTimeCurrent:     'Heure de fin actuelle',
  endTimeRequestBtn:  'Demander un changement d\u2019heure de fin',
  endTimeRequestedNew:'Nouvelle heure de fin demandée',
  endTimeReason:      'Motif (minimum 20 caractères)',
  endTimeSubmit:      'Envoyer la demande',
  endTimePending:     'Demande en attente',
  endTimeApproved:    'Demande approuvée',
  endTimeDenied:      'Demande refusée',
  adminNoteLabel:     'Note de l\u2019administrateur',
  historyEmpty:       'Aucune modification enregistrée pour cette enchère.',
  close:              'Fermer',
  // iter483.3
  lockedByBids:       'Verrouillé — enchères reçues',
  auctionLocked:      'Cette enchère a des offres actives. Pour demander une modification, utilisez le centre de demandes.',
  submitEditRequest:  'Soumettre une demande de modification',
  requestCenter:      'Centre de demandes',
  requestType:        'Type de demande',
  reqEndTime:         'Changement d\u2019heure de fin',
  reqReservePrice:    'Prix de réserve',
  reqEdit:            'Modifier un champ verrouillé',
  reqTarget:          'Cible',
  reqTargetAuction:   'Enchère entière',
  reqTargetLot:       'Lot',
  reqReservePriceInput:'Prix de réserve demandé ($)',
  reqEditField:       'Champ',
  reqEditNewValue:    'Nouvelle valeur demandée',
  reqReason:          'Motif (min 20 caractères)',
  reqSubmit:          'Envoyer la demande',
  reqSubmitted:       'Demande envoyée',
  reqYourRequests:    'Vos demandes',
  reqNone:            'Aucune demande.',
  reqStatusPending:   'En attente',
  reqStatusApproved:  'Approuvée',
  reqStatusDenied:    'Refusée',
  reqDuplicate:       'Une demande en attente de ce type existe déjà',
  unsavedTitle:       'Rejeter les modifications non enregistrées ?',
  unsavedDesc:        'Vous avez des modifications non enregistrées dans cette section. Quitter quand même ?',
  discard:            'Rejeter',
  keepEditing:        'Continuer',
  lotBids:            'enchères',
  lotLockedMsg:       'Ce lot est verrouillé car il a reçu des enchères. Vous ne pouvez plus le modifier directement.',
  lotSectionTitle:    'Lots de cette enchère',
  lotEmpty:           'Cette enchère n\u2019a aucun lot à modifier.',
  lotDropHint:        'Glissez-déposez ou cliquez pour ajouter des photos à ce lot',
};

// ─────────────────────────────────────────────────────────────────────
//  Constants
// ─────────────────────────────────────────────────────────────────────

const ACCEPTED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
const MAX_BYTES = 10 * 1024 * 1024;

const TABS_ORDER = ['info', 'media', 'lots', 'schedule', 'shipping', 'addlot', 'requests', 'history'];

// ─────────────────────────────────────────────────────────────────────
//  Main
// ─────────────────────────────────────────────────────────────────────

export default function SellerLiveEditModal({
  open, onClose, listing, token, onSaved,
}) {
  const { L } = useBilingual();
  const auctionId = listing?.id || listing?._id;
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  // ─── Global auction state (server-hydrated) ─────────────────
  const [title, setTitle] = useState(listing?.title || '');
  const [description, setDescription] = useState(listing?.description || '');
  const [images, setImages] = useState(listing?.images || listing?.photos || []);
  const [schedule, setSchedule] = useState(listing?.schedule || {});
  const [pickup, setPickup] = useState(listing?.pickup || {});
  const [shipping, setShipping] = useState(listing?.shipping || {});
  const [lotsData, setLotsData] = useState([]);           // iter483.3
  const [auctionLocked, setAuctionLocked] = useState(false); // iter483.3
  const [auctionBidCount, setAuctionBidCount] = useState(0); // iter483.3
  const [status, setStatus] = useState(listing?.status || 'active');
  const [endTime, setEndTime] = useState(listing?.end_time || listing?.auction_end_date || '');

  // ─── Section-scoped loading state
  const [savingInfo, setSavingInfo] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [savingShipping, setSavingShipping] = useState(false);

  // ─── Media uploader (auction level)
  const [uploads, setUploads] = useState([]);
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  // ─── Add-lot form
  const [newLot, setNewLot] = useState({
    title: '', description: '', quantity: 1, starting_price: '',
    category: 'other', condition: 'good',
  });
  const [submittingLot, setSubmittingLot] = useState(false);

  // ─── End-time request (kept for pre-fill from Request Center)
  const [newEndTime, setNewEndTime] = useState('');
  const [endTimeReason, setEndTimeReason] = useState('');

  // ─── Request Center
  const [requests, setRequests] = useState([]);
  const [reqForm, setReqForm] = useState({
    request_type: 'end_time',
    target: 'auction',
    payload: {},
    reason: '',
    prefilled_field: null,
  });
  const [submittingReq, setSubmittingReq] = useState(false);

  // ─── History
  const [history, setHistory] = useState([]);

  // ─── Tab + unsaved-changes tracking
  const [tab, setTab] = useState('info');
  const [dirtySection, setDirtySection] = useState(null); // 'info' | 'schedule' | 'shipping' | null
  const [confirmDiscard, setConfirmDiscard] = useState(null); // { target_tab }

  // ─── Hydrate on open (fresh DB read)
  useEffect(() => {
    if (!open || !auctionId) return;
    (async () => {
      try {
        const [hr, sr, rr] = await Promise.all([
          axios.get(`${API}/auctions/${auctionId}/edited-history`, { headers }),
          axios.get(`${API}/auctions/${auctionId}/edit-state`, { headers }),
          axios.get(`${API}/auctions/${auctionId}/requests`, { headers }),
        ]);
        setHistory(hr.data?.history || []);

        const s = sr.data || {};
        setTitle(s.title || '');
        setDescription(s.description || '');
        setImages(Array.isArray(s.images) ? s.images : []);
        setSchedule(s.schedule || {});
        setPickup(s.pickup || {});
        setShipping(s.shipping || {});
        setLotsData(Array.isArray(s.lots) ? s.lots : []);
        setAuctionLocked(Boolean(s.auction_locked));
        setAuctionBidCount(Number(s.bid_count || 0));
        setStatus(s.status || 'active');
        setEndTime(s.end_time || '');

        setRequests(rr.data?.rows || []);
      } catch (_) { /* soft */ }
    })();
  }, [open, auctionId, headers]);

  // ─── PATCH helper
  const patchField = useCallback(async (field, value) => {
    try {
      const r = await axios.patch(
        `${API}/auctions/${auctionId}/live-edit`,
        { field, value },
        { headers },
      );
      toast.success(L.savedOk);
      if (typeof onSaved === 'function') onSaved(field, r.data.new_value);
      return r.data;
    } catch (e) {
      const msg = e.response?.data?.detail || L.saveFailed;
      // Auction bid lock hint
      if (typeof msg === 'string' && msg.includes('auction_has_bids')) {
        toast.error(L.auctionLocked);
      } else if (typeof msg === 'string' && msg.includes('lot_has_bids')) {
        toast.error(L.lotLockedMsg);
      } else {
        toast.error(typeof msg === 'string' ? msg : L.saveFailed);
      }
      throw e;
    }
  }, [auctionId, headers, L, onSaved]);

  // ─── Info save
  const saveInfo = async () => {
    setSavingInfo(true);
    try {
      if (title !== (listing?.title || '')) await patchField('title', title);
      if (description !== (listing?.description || '')) await patchField('description', description);
      setDirtySection(null);
    } finally {
      setSavingInfo(false);
    }
  };

  // ─── Media uploader (auction level)
  const removeImage = async (url) => {
    try {
      const r = await patchField('images', { remove: [url] });
      setImages(r.new_value);
    } catch (_) { /* toast already shown */ }
  };

  const uploadAuctionImages = async (fileList) => {
    await _uploadImages(fileList, async (url) => {
      const patched = await patchField('images', { add: [url] });
      setImages(patched.new_value);
    });
  };

  const _uploadImages = async (fileList, onUploaded) => {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;

    const trackers = files.map((f) => {
      let rejection = null;
      if (!ACCEPTED_TYPES.includes(f.type)) rejection = L.uploadRejectedType;
      else if (f.size > MAX_BYTES) rejection = L.uploadRejectedSize;
      return {
        id: `${f.name}-${f.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name, pct: 0,
        status: rejection ? 'error' : 'uploading',
        error: rejection,
        file: rejection ? null : f,
      };
    });
    setUploads((prev) => [...prev, ...trackers]);

    trackers.filter((t) => t.status === 'error').forEach((t) => {
      toast.error(`${t.name} — ${t.error}`);
    });

    for (const t of trackers) {
      if (t.status !== 'uploading') continue;
      const form = new FormData();
      form.append('file', t.file);
      try {
        const res = await axios.post(`${API}/uploads/listing-image`, form, {
          headers: { ...headers, 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (evt) => {
            if (evt.total) {
              const pct = Math.round((evt.loaded * 100) / evt.total);
              setUploads((prev) => prev.map((row) =>
                row.id === t.id ? { ...row, pct } : row));
            }
          },
        });
        const url = res?.data?.url;
        if (!url) throw new Error('missing_url_in_response');
        await onUploaded(url, t);
        setUploads((prev) => prev.map((row) =>
          row.id === t.id ? { ...row, pct: 100, status: 'done' } : row));
      } catch (err) {
        const reason = err?.response?.data?.detail?.message_en
                    || err?.response?.data?.detail?.detail
                    || err?.response?.data?.detail
                    || err?.message
                    || L.uploadFailed;
        toast.error(`${t.name} — ${typeof reason === 'string' ? reason : L.uploadFailed}`);
        setUploads((prev) => prev.map((row) =>
          row.id === t.id
            ? { ...row, status: 'error', error: typeof reason === 'string' ? reason : L.uploadFailed }
            : row));
      }
    }
  };

  // ─── Schedule / Shipping save
  const saveSchedule = async () => {
    setSavingSchedule(true);
    try {
      await patchField('schedule', schedule);
      await patchField('pickup', pickup);
      setDirtySection(null);
    } finally {
      setSavingSchedule(false);
    }
  };
  const saveShipping = async () => {
    setSavingShipping(true);
    try {
      await patchField('shipping', shipping);
      setDirtySection(null);
    } finally {
      setSavingShipping(false);
    }
  };

  // ─── Add lot
  const submitNewLot = async () => {
    setSubmittingLot(true);
    try {
      await axios.post(
        `${API}/auctions/${auctionId}/lots`,
        { lot: { ...newLot,
                 starting_price: parseFloat(newLot.starting_price || 0) } },
        { headers });
      toast.success(L.newLotPending);
      setNewLot({ title: '', description: '', quantity: 1,
                  starting_price: '', category: 'other', condition: 'good' });
    } catch (e) {
      const msg = e.response?.data?.detail || L.saveFailed;
      toast.error(typeof msg === 'string' ? msg : L.saveFailed);
    } finally {
      setSubmittingLot(false);
    }
  };

  // ─── Request Center: submit a request
  const submitRequest = async () => {
    setSubmittingReq(true);
    try {
      const body = {
        request_type: reqForm.request_type,
        target: reqForm.target || 'auction',
        payload: reqForm.payload || {},
        reason: reqForm.reason || '',
      };
      if (reqForm.request_type === 'end_time' && newEndTime) {
        body.payload = { requested_end_time: new Date(newEndTime).toISOString() };
        body.reason = endTimeReason || body.reason;
      }
      const r = await axios.post(
        `${API}/auctions/${auctionId}/requests`, body, { headers });
      toast.success(L.reqSubmitted);
      setRequests((prev) => [r.data, ...prev]);
      setReqForm({ request_type: 'end_time', target: 'auction',
                   payload: {}, reason: '', prefilled_field: null });
      setNewEndTime('');
      setEndTimeReason('');
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || L.saveFailed);
      toast.error(e.response?.status === 409 ? L.reqDuplicate : msg);
    } finally {
      setSubmittingReq(false);
    }
  };

  // ─── Auction-level lock warning banner + "Submit Edit Request" pre-fill
  const startEditRequestFor = (fieldName) => {
    setReqForm({
      request_type: 'edit',
      target: 'auction',
      payload: { field_name: fieldName, requested_new_value: '' },
      reason: '',
      prefilled_field: fieldName,
    });
    switchTab('requests');
  };

  // ─── Tab switching with unsaved-changes guard
  const switchTab = (nextTab) => {
    if (dirtySection && dirtySection !== nextTab && dirtySection === tab) {
      setConfirmDiscard({ target_tab: nextTab });
    } else {
      setTab(nextTab);
    }
  };

  const confirmDiscardChanges = () => {
    setDirtySection(null);
    if (confirmDiscard?.target_tab) setTab(confirmDiscard.target_tab);
    setConfirmDiscard(null);
  };

  const markDirty = (section) => setDirtySection(section);

  // ─── Media dropzone events (auction-level)
  const onDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer?.files?.length) uploadAuctionImages(e.dataTransfer.files);
  };
  const onDragOver = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true); };
  const onDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); };
  const onPickFile = (e) => { if (e.target.files?.length) uploadAuctionImages(e.target.files); e.target.value = ''; };

  // ─────────────────────────────────────────────────────────────
  //  Rendering
  // ─────────────────────────────────────────────────────────────

  if (!open || !auctionId) return null;

  const isMultiLot = Array.isArray(lotsData) && lotsData.length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent
        className="p-0 gap-0 max-w-none sm:max-w-2xl lg:max-w-4xl h-[100dvh] sm:h-[90vh] sm:rounded-lg overflow-hidden flex flex-col"
        data-testid="seller-live-edit-modal"
      >
        {/* Header */}
        <DialogHeader className="p-4 sm:p-6 pb-2 border-b flex-shrink-0">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <DialogTitle className="text-lg sm:text-xl font-semibold flex items-center gap-2">
                {L.title}
                {auctionLocked && (
                  <Badge
                    variant="outline"
                    className="bg-amber-100 text-amber-800 border-amber-300"
                    data-testid="auction-locked-badge"
                  >
                    <Lock className="h-3 w-3 mr-1" />
                    {auctionBidCount} {L.lotBids}
                  </Badge>
                )}
              </DialogTitle>
              <DialogDescription className="text-xs truncate">
                {title || auctionId}
              </DialogDescription>
            </div>
            <Button
              variant="ghost" size="icon"
              onClick={onClose}
              data-testid="modal-close-btn"
              className="flex-shrink-0"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Tabs — horizontal scrollable pill row (mobile-first) */}
          <div
            className="flex gap-1.5 overflow-x-auto pt-3 no-scrollbar -mx-4 px-4 sm:-mx-6 sm:px-6"
            data-testid="edit-tabs"
          >
            {TABS_ORDER.map((t) => {
              // hide Lots + Add Lot tabs on single-lot auctions
              if ((t === 'lots' || t === 'addlot') && !isMultiLot) return null;
              const active = tab === t;
              const label = ({
                info:    { icon: FileText,     text: L.info },
                media:   { icon: Upload,       text: L.media },
                lots:    { icon: Package,      text: L.lots },
                schedule:{ icon: Calendar,     text: L.schedule },
                shipping:{ icon: Truck,        text: L.shipping },
                addlot:  { icon: Plus,         text: L.addLot },
                requests:{ icon: MessageSquare,text: L.requests },
                history: { icon: History,      text: L.history },
              })[t];
              const Icon = label.icon;
              return (
                <button
                  key={t}
                  onClick={() => switchTab(t)}
                  data-testid={`edit-tab-${t}`}
                  className={`flex-shrink-0 whitespace-nowrap px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition inline-flex items-center gap-1.5 ${
                    active
                      ? 'bg-blue-600 text-white shadow'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-200'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label.text}
                </button>
              );
            })}
          </div>
        </DialogHeader>

        {/* Body — scrollable */}
        <div
          className="flex-1 overflow-y-auto p-4 sm:p-6 pb-24 sm:pb-6"
          data-testid="edit-body"
        >
          {tab === 'info' && (
            <SectionInfo
              L={L} title={title} description={description}
              setTitle={(v) => { setTitle(v); markDirty('info'); }}
              setDescription={(v) => { setDescription(v); markDirty('info'); }}
              auctionLocked={auctionLocked}
              startEditRequestFor={startEditRequestFor}
              saving={savingInfo} onSave={saveInfo}
            />
          )}
          {tab === 'media' && (
            <SectionMedia
              L={L} images={images} uploads={uploads}
              dragActive={dragActive}
              onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}
              onPickFile={onPickFile}
              fileInputRef={fileInputRef}
              onRemove={removeImage}
            />
          )}
          {tab === 'lots' && isMultiLot && (
            <SectionLots
              L={L}
              lots={lotsData}
              auctionId={auctionId}
              headers={headers}
              patchField={patchField}
              refreshLots={async () => {
                try {
                  const sr = await axios.get(`${API}/auctions/${auctionId}/edit-state`, { headers });
                  setLotsData(sr.data?.lots || []);
                } catch (_) { /* soft */ }
              }}
              startReserveRequestForLot={(lotRef) => {
                setReqForm({
                  request_type: 'reserve_price',
                  target: String(lotRef),
                  payload: { requested_reserve_price: '' },
                  reason: '', prefilled_field: null,
                });
                switchTab('requests');
              }}
            />
          )}
          {tab === 'schedule' && (
            <SectionSchedule
              L={L}
              schedule={schedule} setSchedule={(v) => { setSchedule(v); markDirty('schedule'); }}
              pickup={pickup} setPickup={(v) => { setPickup(v); markDirty('schedule'); }}
              auctionLocked={auctionLocked}
              startEditRequestFor={startEditRequestFor}
              saving={savingSchedule} onSave={saveSchedule}
            />
          )}
          {tab === 'shipping' && (
            <SectionShipping
              L={L}
              shipping={shipping} setShipping={(v) => { setShipping(v); markDirty('shipping'); }}
              auctionLocked={auctionLocked}
              startEditRequestFor={startEditRequestFor}
              saving={savingShipping} onSave={saveShipping}
            />
          )}
          {tab === 'addlot' && isMultiLot && (
            <SectionAddLot
              L={L} newLot={newLot} setNewLot={setNewLot}
              submitting={submittingLot} onSubmit={submitNewLot}
            />
          )}
          {tab === 'requests' && (
            <SectionRequests
              L={L}
              reqForm={reqForm} setReqForm={setReqForm}
              lotsData={lotsData}
              endTime={endTime}
              newEndTime={newEndTime} setNewEndTime={setNewEndTime}
              endTimeReason={endTimeReason} setEndTimeReason={setEndTimeReason}
              submitting={submittingReq} onSubmit={submitRequest}
              requests={requests}
            />
          )}
          {tab === 'history' && (
            <SectionHistory L={L} history={history} />
          )}
        </div>
      </DialogContent>

      {/* Unsaved-changes confirm dialog */}
      <AlertDialog open={!!confirmDiscard} onOpenChange={(o) => { if (!o) setConfirmDiscard(null); }}>
        <AlertDialogContent data-testid="unsaved-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{L.unsavedTitle}</AlertDialogTitle>
            <AlertDialogDescription>{L.unsavedDesc}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="unsaved-keep-editing-btn">{L.keepEditing}</AlertDialogCancel>
            <AlertDialogAction data-testid="unsaved-discard-btn" onClick={confirmDiscardChanges}>
              {L.discard}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  Section sub-components
// ─────────────────────────────────────────────────────────────────────

function LockNotice({ L, onRequest, field }) {
  return (
    <div
      className="border border-amber-300 bg-amber-50 dark:bg-amber-950/30 rounded p-3 my-2 flex items-start gap-2"
      data-testid={`auction-locked-notice-${field}`}
    >
      <Lock className="h-4 w-4 text-amber-700 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-amber-900 dark:text-amber-100">{L.auctionLocked}</p>
        <Button
          size="sm" variant="outline"
          className="mt-2 bg-white/70"
          onClick={() => onRequest(field)}
          data-testid={`submit-edit-request-btn-${field}`}
        >
          <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
          {L.submitEditRequest}
        </Button>
      </div>
    </div>
  );
}

function StickySave({ children }) {
  return (
    <div className="sm:hidden fixed bottom-0 left-0 right-0 p-3 bg-white dark:bg-slate-900 border-t z-10">
      {children}
    </div>
  );
}

function SectionInfo({ L, title, description, setTitle, setDescription, auctionLocked, startEditRequestFor, saving, onSave }) {
  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="edit-title-input">{L.fieldTitle}</Label>
        {auctionLocked && <LockNotice L={L} onRequest={startEditRequestFor} field="title" />}
        <Input
          id="edit-title-input" data-testid="edit-title-input"
          value={title} onChange={(e) => setTitle(e.target.value)}
          disabled={auctionLocked}
          className={auctionLocked ? 'opacity-60' : ''}
        />
      </div>
      <div>
        <Label htmlFor="edit-description-input">{L.fieldDescription}</Label>
        {auctionLocked && <LockNotice L={L} onRequest={startEditRequestFor} field="description" />}
        <Textarea
          id="edit-description-input" data-testid="edit-description-input"
          rows={6} value={description} onChange={(e) => setDescription(e.target.value)}
          disabled={auctionLocked}
          className={auctionLocked ? 'opacity-60' : ''}
        />
      </div>
      {!auctionLocked && (
        <>
          <Button
            onClick={onSave} disabled={saving}
            data-testid="save-info-btn"
            className="hidden sm:inline-flex bg-blue-600 hover:bg-blue-700 text-white"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            {L.saveInfo}
          </Button>
          <StickySave>
            <Button onClick={onSave} disabled={saving} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-info-btn-mobile">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {L.saveInfo}
            </Button>
          </StickySave>
        </>
      )}
    </div>
  );
}

function Dropzone({ L, dragActive, onDrop, onDragOver, onDragLeave, onPickFile, fileInputRef, disabled, testidPrefix, hintOverride }) {
  return (
    <div
      role="button" tabIndex={0}
      onClick={() => !disabled && fileInputRef.current?.click()}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !disabled) fileInputRef.current?.click(); }}
      onDrop={disabled ? (e) => e.preventDefault() : onDrop}
      onDragOver={disabled ? (e) => e.preventDefault() : onDragOver}
      onDragLeave={disabled ? (e) => e.preventDefault() : onDragLeave}
      data-testid={`${testidPrefix}-dropzone`}
      className={`border-2 border-dashed rounded-lg p-4 sm:p-6 text-center transition min-h-[120px] flex flex-col justify-center ${
        disabled
          ? 'border-slate-200 bg-slate-100 opacity-50 cursor-not-allowed'
          : dragActive
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 cursor-pointer'
            : 'border-slate-300 hover:border-blue-400 bg-slate-50 dark:bg-slate-800 cursor-pointer'
      }`}
    >
      {disabled ? (
        <>
          <Lock className="h-6 w-6 mx-auto text-slate-400 mb-1" />
          <p className="text-sm text-slate-500">{L.lotLockedMsg}</p>
        </>
      ) : (
        <>
          <Upload className="h-6 w-6 sm:h-8 sm:w-8 mx-auto text-slate-500 mb-2" />
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{hintOverride || L.uploadHint}</p>
          <p className="text-xs text-slate-500 mt-1">{L.uploadAccepted}</p>
        </>
      )}
      <input
        ref={fileInputRef} type="file"
        accept="image/jpeg,image/jpg,image/png,image/webp"
        multiple onChange={onPickFile}
        className="hidden"
        data-testid={`${testidPrefix}-input`}
      />
    </div>
  );
}

function UploadProgressList({ L, uploads }) {
  if (!uploads?.length) return null;
  return (
    <div className="space-y-2" data-testid="image-upload-progress">
      {uploads.map((u) => (
        <div key={u.id}
             className="border rounded p-2 text-sm bg-white dark:bg-slate-900"
             data-testid={`image-upload-row-${u.status}`}>
          <div className="flex justify-between items-center mb-1">
            <span className="truncate max-w-xs">{u.name}</span>
            <span className={
              u.status === 'error' ? 'text-rose-600 text-xs'
                : u.status === 'done' ? 'text-emerald-600 text-xs'
                : 'text-slate-500 text-xs'
            }>
              {u.status === 'error' ? u.error : u.status === 'done' ? '✓' : `${u.pct}%`}
            </span>
          </div>
          {u.status === 'uploading' && (
            <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
              <div className="bg-blue-600 h-1.5 transition-all" style={{ width: `${u.pct}%` }} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SectionMedia({ L, images, uploads, dragActive, onDrop, onDragOver, onDragLeave, onPickFile, fileInputRef, onRemove }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">{L.removeOwnOnly}</p>
      <Dropzone
        L={L} dragActive={dragActive} onDrop={onDrop} onDragOver={onDragOver}
        onDragLeave={onDragLeave} onPickFile={onPickFile} fileInputRef={fileInputRef}
        testidPrefix="image-uploader"
      />
      <UploadProgressList L={L} uploads={uploads} />
      <div>
        <Label>{L.currentImages} ({images.length})</Label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-2">
          {images.map((url, i) => {
            const src = typeof url === 'string' ? url : url?.url;
            return (
              <div key={`${src}-${i}`} className="relative group">
                <img src={src} alt="" className="w-full h-24 object-cover rounded" />
                <Button size="sm" variant="destructive"
                        onClick={() => onRemove(src)}
                        className="absolute top-1 right-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition h-6 w-6 p-0"
                        data-testid={`remove-image-btn-${i}`}>
                  <X className="h-3 w-3" />
                </Button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SectionLots({ L, lots, auctionId, headers, patchField, refreshLots, startReserveRequestForLot }) {
  return (
    <div className="space-y-4" data-testid="section-lots">
      <h3 className="font-semibold text-slate-800 dark:text-slate-100">{L.lotSectionTitle}</h3>
      {lots.length === 0 && (
        <p className="text-center text-slate-500 italic py-8">{L.lotEmpty}</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {lots.map((lot) => (
          <LotCard
            key={lot.id || lot.lot_number}
            L={L} lot={lot} auctionId={auctionId} headers={headers}
            patchField={patchField}
            refreshLots={refreshLots}
            startReserveRequestForLot={startReserveRequestForLot}
          />
        ))}
      </div>
    </div>
  );
}

function LotCard({ L, lot, auctionId, headers, patchField, refreshLots, startReserveRequestForLot }) {
  const locked = Boolean(lot.locked || (Number(lot.bid_count) || 0) > 0);
  const [uploads, setUploads] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const fileRef = useRef(null);
  const lotRef = lot.id || lot.lot_number;

  const uploadFilesForLot = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const trackers = files.map((f) => {
      let rejection = null;
      if (!ACCEPTED_TYPES.includes(f.type)) rejection = L.uploadRejectedType;
      else if (f.size > MAX_BYTES) rejection = L.uploadRejectedSize;
      return {
        id: `${f.name}-${f.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name, pct: 0,
        status: rejection ? 'error' : 'uploading',
        error: rejection, file: rejection ? null : f,
      };
    });
    setUploads((prev) => [...prev, ...trackers]);

    trackers.filter((t) => t.status === 'error').forEach((t) =>
      toast.error(`${t.name} — ${t.error}`));

    for (const t of trackers) {
      if (t.status !== 'uploading') continue;
      const form = new FormData();
      form.append('file', t.file);
      try {
        const res = await axios.post(`${API}/uploads/listing-image`, form, {
          headers: { ...headers, 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (evt) => {
            if (evt.total) {
              const pct = Math.round((evt.loaded * 100) / evt.total);
              setUploads((prev) => prev.map((row) => row.id === t.id ? { ...row, pct } : row));
            }
          },
        });
        const url = res?.data?.url;
        if (!url) throw new Error('missing_url_in_response');
        await patchField('lot_image_add', { lot_id: lotRef, image_url: url });
        setUploads((prev) => prev.map((row) =>
          row.id === t.id ? { ...row, pct: 100, status: 'done' } : row));
        await refreshLots();
      } catch (err) {
        const reason = err?.response?.data?.detail || err?.message || L.uploadFailed;
        toast.error(`${t.name} — ${typeof reason === 'string' ? reason : L.uploadFailed}`);
        setUploads((prev) => prev.map((row) =>
          row.id === t.id
            ? { ...row, status: 'error', error: typeof reason === 'string' ? reason : L.uploadFailed }
            : row));
      }
    }
  };

  const onDrop = (e) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer?.files?.length) uploadFilesForLot(e.dataTransfer.files); };
  const onDragOver = (e) => { e.preventDefault(); setDragActive(true); };
  const onDragLeave = (e) => { e.preventDefault(); setDragActive(false); };
  const onPickFile = (e) => { if (e.target.files?.length) uploadFilesForLot(e.target.files); e.target.value = ''; };

  const removeLotImage = async (url) => {
    if (locked) return;
    try {
      await patchField('lot_image_remove', { lot_id: lotRef, image_url: url });
      await refreshLots();
    } catch (_) { /* toast shown */ }
  };

  return (
    <div
      className={`border rounded-lg p-4 bg-white dark:bg-slate-900 space-y-3 ${
        locked ? 'ring-1 ring-amber-300' : ''
      }`}
      data-testid={`lot-card-${lotRef}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline">Lot #{lot.lot_number ?? '—'}</Badge>
            {locked && (
              <Badge className="bg-amber-100 text-amber-800 border-amber-300" data-testid={`lot-locked-badge-${lotRef}`}>
                <Lock className="h-3 w-3 mr-1" /> {L.lockedByBids}
              </Badge>
            )}
          </div>
          <h4 className="font-medium truncate mt-1">{lot.title || '(untitled)'}</h4>
          <p className="text-xs text-slate-500 truncate">
            Qty: {lot.quantity ?? 1} · Start: ${lot.starting_price ?? 0} · Bids: {lot.bid_count ?? 0}
            {lot.reserve_price != null && ` · Reserve: $${lot.reserve_price}`}
          </p>
        </div>
      </div>

      {/* Per-lot uploader */}
      <Dropzone
        L={L}
        dragActive={dragActive} onDrop={onDrop} onDragOver={onDragOver}
        onDragLeave={onDragLeave} onPickFile={onPickFile}
        fileInputRef={fileRef}
        disabled={locked}
        testidPrefix={`lot-uploader-${lotRef}`}
        hintOverride={L.lotDropHint}
      />
      <UploadProgressList L={L} uploads={uploads} />

      {/* Current lot images grid */}
      {Array.isArray(lot.images) && lot.images.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {lot.images.map((url, i) => (
            <div key={`${url}-${i}`} className="relative group">
              <img src={url} alt="" className="w-full h-20 object-cover rounded" />
              {!locked && (
                <Button
                  size="sm" variant="destructive"
                  onClick={() => removeLotImage(url)}
                  className="absolute top-1 right-1 h-6 w-6 p-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition"
                  data-testid={`lot-remove-image-btn-${lotRef}-${i}`}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Request reserve price for this lot */}
      {!locked && (
        <Button
          size="sm" variant="outline"
          onClick={() => startReserveRequestForLot(lotRef)}
          data-testid={`lot-request-reserve-btn-${lotRef}`}
          className="w-full sm:w-auto"
        >
          <DollarSign className="h-3.5 w-3.5 mr-1.5" />
          {L.reqReservePrice}
        </Button>
      )}
    </div>
  );
}

function SectionSchedule({ L, schedule, setSchedule, pickup, setPickup, auctionLocked, startEditRequestFor, saving, onSave }) {
  return (
    <div className="space-y-4">
      {auctionLocked && <LockNotice L={L} onRequest={startEditRequestFor} field="schedule" />}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <Label>{L.previewDate}</Label>
          <Input type="date" data-testid="preview-date-input"
                 value={schedule.preview_date || ''} disabled={auctionLocked}
                 onChange={(e) => setSchedule({ ...schedule, preview_date: e.target.value })} />
        </div>
        <div>
          <Label>{L.previewTime}</Label>
          <Input type="time" data-testid="preview-time-input"
                 value={schedule.preview_time || ''} disabled={auctionLocked}
                 onChange={(e) => setSchedule({ ...schedule, preview_time: e.target.value })} />
        </div>
      </div>
      <div>
        <Label>{L.pickupLocation}</Label>
        <Input data-testid="pickup-location-input"
               value={pickup.location || ''} disabled={auctionLocked}
               onChange={(e) => setPickup({ ...pickup, location: e.target.value })} />
      </div>
      <div>
        <Label>{L.pickupInstructions}</Label>
        <Textarea rows={3} data-testid="pickup-instructions-input"
                  value={pickup.instructions || ''} disabled={auctionLocked}
                  onChange={(e) => setPickup({ ...pickup, instructions: e.target.value })} />
      </div>
      {!auctionLocked && (
        <>
          <Button onClick={onSave} disabled={saving}
                  className="hidden sm:inline-flex bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="save-schedule-btn">
            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            {L.saveSchedule}
          </Button>
          <StickySave>
            <Button onClick={onSave} disabled={saving} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-schedule-btn-mobile">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {L.saveSchedule}
            </Button>
          </StickySave>
        </>
      )}
    </div>
  );
}

function SectionShipping({ L, shipping, setShipping, auctionLocked, startEditRequestFor, saving, onSave }) {
  return (
    <div className="space-y-4">
      {auctionLocked && <LockNotice L={L} onRequest={startEditRequestFor} field="shipping" />}
      <div className="flex items-center gap-2">
        <Checkbox
          id="shipping-available"
          data-testid="shipping-available-toggle"
          disabled={auctionLocked}
          checked={!!shipping.available}
          onCheckedChange={(v) => setShipping({ ...shipping, available: !!v })}
        />
        <Label htmlFor="shipping-available">{L.shippingAvailable}</Label>
      </div>
      <div>
        <Label>{L.carrier}</Label>
        <Input value={shipping.carrier || ''} disabled={auctionLocked}
               onChange={(e) => setShipping({ ...shipping, carrier: e.target.value })} />
      </div>
      <div>
        <Label>{L.shippingNotes}</Label>
        <Textarea rows={3} data-testid="shipping-notes-input"
                  value={shipping.notes || ''} disabled={auctionLocked}
                  onChange={(e) => setShipping({ ...shipping, notes: e.target.value })} />
      </div>
      <div>
        <Label>{L.shippingEstimate}</Label>
        <Input value={shipping.estimated_cost || ''} disabled={auctionLocked}
               data-testid="shipping-estimate-input"
               onChange={(e) => setShipping({ ...shipping, estimated_cost: e.target.value })} />
        <p className="text-xs text-slate-500 mt-1">{L.shippingEstimateHelp}</p>
      </div>
      {!auctionLocked && (
        <>
          <Button onClick={onSave} disabled={saving}
                  className="hidden sm:inline-flex bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="save-shipping-btn">
            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            {L.saveShipping}
          </Button>
          <StickySave>
            <Button onClick={onSave} disabled={saving} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-shipping-btn-mobile">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {L.saveShipping}
            </Button>
          </StickySave>
        </>
      )}
    </div>
  );
}

function SectionAddLot({ L, newLot, setNewLot, submitting, onSubmit }) {
  return (
    <div className="space-y-3">
      <div>
        <Label>{L.newLotTitle}</Label>
        <Input data-testid="new-lot-title"
               value={newLot.title}
               onChange={(e) => setNewLot({ ...newLot, title: e.target.value })} />
      </div>
      <div>
        <Label>{L.newLotDescription}</Label>
        <Textarea rows={3} data-testid="new-lot-description"
                  value={newLot.description}
                  onChange={(e) => setNewLot({ ...newLot, description: e.target.value })} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <Label>{L.newLotQuantity}</Label>
          <Input type="number" min={1} data-testid="new-lot-quantity"
                 value={newLot.quantity}
                 onChange={(e) => setNewLot({ ...newLot, quantity: parseInt(e.target.value, 10) || 1 })} />
        </div>
        <div>
          <Label>{L.newLotStartPrice}</Label>
          <Input type="number" step="0.01" data-testid="new-lot-start-price"
                 value={newLot.starting_price}
                 onChange={(e) => setNewLot({ ...newLot, starting_price: e.target.value })} />
        </div>
      </div>
      <Button onClick={onSubmit} disabled={submitting || !newLot.title?.trim()}
              data-testid="submit-new-lot-btn"
              className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white">
        {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
        {L.submitNewLot}
      </Button>
    </div>
  );
}

function SectionRequests({
  L, reqForm, setReqForm, lotsData,
  endTime, newEndTime, setNewEndTime,
  endTimeReason, setEndTimeReason,
  submitting, onSubmit, requests,
}) {
  const REQUEST_TYPES = [
    { value: 'end_time',      label: L.reqEndTime,      icon: Clock },
    { value: 'reserve_price', label: L.reqReservePrice, icon: DollarSign },
    { value: 'edit',          label: L.reqEdit,         icon: FileText },
  ];
  const EDIT_FIELDS = ['title', 'description', 'schedule', 'pickup', 'shipping'];

  const isEndTime = reqForm.request_type === 'end_time';
  const isReserve = reqForm.request_type === 'reserve_price';
  const isEdit    = reqForm.request_type === 'edit';

  const setPayload = (patch) =>
    setReqForm((prev) => ({ ...prev, payload: { ...(prev.payload || {}), ...patch } }));

  return (
    <div className="space-y-4">
      <h3 className="font-semibold" data-testid="request-center-title">{L.requestCenter}</h3>

      {/* Request-type picker */}
      <div>
        <Label>{L.requestType}</Label>
        <div className="flex flex-wrap gap-2 mt-1">
          {REQUEST_TYPES.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setReqForm((p) => ({
                ...p,
                request_type: value,
                target: 'auction',
                payload: {},
                prefilled_field: null,
              }))}
              data-testid={`request-type-${value}`}
              className={`px-3 py-1.5 rounded-full text-sm font-medium inline-flex items-center gap-1.5 transition ${
                reqForm.request_type === value
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Target picker (reserve_price can target lot; edit is always auction) */}
      {isReserve && (
        <div>
          <Label>{L.reqTarget}</Label>
          <select
            value={reqForm.target || 'auction'}
            onChange={(e) => setReqForm((p) => ({ ...p, target: e.target.value }))}
            data-testid="request-target"
            className="mt-1 w-full border rounded px-3 py-2 bg-white dark:bg-slate-800"
          >
            <option value="auction">{L.reqTargetAuction}</option>
            {lotsData.map((lot) => (
              <option
                key={lot.id || lot.lot_number}
                value={String(lot.id || lot.lot_number)}
              >
                {L.reqTargetLot} #{lot.lot_number} — {lot.title || '(untitled)'}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Type-specific payload inputs */}
      {isEndTime && (
        <>
          <div className="text-xs text-slate-500">
            {L.endTimeCurrent}: <span className="font-mono">{endTime || '—'}</span>
          </div>
          <div>
            <Label>{L.endTimeRequestedNew}</Label>
            <Input type="datetime-local" data-testid="new-end-time-input"
                   value={newEndTime} onChange={(e) => setNewEndTime(e.target.value)} />
          </div>
          <div>
            <Label>{L.endTimeReason}</Label>
            <Textarea rows={3} minLength={20} data-testid="end-time-reason-input"
                      value={endTimeReason} onChange={(e) => setEndTimeReason(e.target.value)} />
          </div>
        </>
      )}

      {isReserve && (
        <>
          <div>
            <Label>{L.reqReservePriceInput}</Label>
            <Input type="number" step="0.01" min="0"
                   data-testid="reserve-price-input"
                   value={reqForm.payload?.requested_reserve_price ?? ''}
                   onChange={(e) => setPayload({ requested_reserve_price: e.target.value })} />
          </div>
          <div>
            <Label>{L.reqReason}</Label>
            <Textarea rows={3} minLength={20} data-testid="request-reason-input"
                      value={reqForm.reason || ''}
                      onChange={(e) => setReqForm((p) => ({ ...p, reason: e.target.value }))} />
          </div>
        </>
      )}

      {isEdit && (
        <>
          <div>
            <Label>{L.reqEditField}</Label>
            <select
              value={reqForm.payload?.field_name || ''}
              onChange={(e) => setPayload({ field_name: e.target.value })}
              data-testid="edit-field-name"
              className="mt-1 w-full border rounded px-3 py-2 bg-white dark:bg-slate-800"
            >
              <option value="">—</option>
              {EDIT_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <div>
            <Label>{L.reqEditNewValue}</Label>
            <Input data-testid="edit-new-value"
                   value={reqForm.payload?.requested_new_value ?? ''}
                   onChange={(e) => setPayload({ requested_new_value: e.target.value })} />
          </div>
          <div>
            <Label>{L.reqReason}</Label>
            <Textarea rows={3} minLength={20} data-testid="request-reason-input"
                      value={reqForm.reason || ''}
                      onChange={(e) => setReqForm((p) => ({ ...p, reason: e.target.value }))} />
          </div>
        </>
      )}

      <Button
        onClick={onSubmit} disabled={submitting}
        data-testid="submit-request-btn"
        className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white"
      >
        {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <MessageSquare className="h-4 w-4 mr-2" />}
        {L.reqSubmit}
      </Button>

      {/* Your requests list */}
      <div className="pt-4 border-t mt-4">
        <h4 className="font-medium mb-2">{L.reqYourRequests}</h4>
        {requests.length === 0 && <p className="text-sm text-slate-500 italic">{L.reqNone}</p>}
        <div className="space-y-2" data-testid="own-requests-list">
          {requests.map((r) => (
            <div key={r.id} className="border rounded p-3 text-sm bg-slate-50 dark:bg-slate-800"
                 data-testid={`own-request-row-${r.id}`}>
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline">{r.request_type}</Badge>
                  {r.status === 'pending'  && <Badge className="bg-amber-100 text-amber-800 border-amber-300"><Clock className="h-3 w-3 mr-1 inline" />{L.reqStatusPending}</Badge>}
                  {r.status === 'approved' && <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300"><Check className="h-3 w-3 mr-1 inline" />{L.reqStatusApproved}</Badge>}
                  {r.status === 'denied'   && <Badge className="bg-rose-100 text-rose-800 border-rose-300"><X className="h-3 w-3 mr-1 inline" />{L.reqStatusDenied}</Badge>}
                </div>
                <span className="text-xs text-slate-500 font-mono">{r.submitted_at?.slice(0, 19).replace('T', ' ')}</span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 whitespace-pre-wrap">{r.reason}</p>
              {r.admin_note && (
                <p className="text-xs italic text-slate-500 mt-1">{L.adminNoteLabel}: {r.admin_note}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SectionHistory({ L, history }) {
  if (!history?.length) {
    return <p className="text-sm text-slate-500 italic">{L.historyEmpty}</p>;
  }
  return (
    <div className="space-y-2" data-testid="edit-history-panel">
      {history.slice().reverse().map((h, i) => (
        <details key={h.id || i} className="border rounded p-2 text-sm bg-slate-50 dark:bg-slate-800">
          <summary className="cursor-pointer flex justify-between">
            <span className="font-medium">{h.field}</span>
            <span className="text-xs text-slate-500 font-mono">{h.edited_at}</span>
          </summary>
          <div className="mt-2 text-xs space-y-1">
            <div><span className="text-slate-500">from:</span> <code className="break-all">{JSON.stringify(h.old_value)?.slice(0, 200)}</code></div>
            <div><span className="text-slate-500">to:</span>   <code className="break-all">{JSON.stringify(h.new_value)?.slice(0, 200)}</code></div>
          </div>
        </details>
      ))}
    </div>
  );
}
