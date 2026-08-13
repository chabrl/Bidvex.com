/**
 * iter483 — Seller Live Edit Modal
 * ================================
 *
 * Restricted, non-financial edit surface for an active auction owned
 * by the current seller.  Wraps the six permitted-edit sections
 * (title / description / images / schedule / pickup / shipping / add-lot)
 * plus the End-Time Change Request flow.
 *
 * Backend contract (routes/live_edit.py):
 *   PATCH /api/auctions/{id}/live-edit         {field, value}
 *   POST  /api/auctions/{id}/lots              {lot: {...}}
 *   POST  /api/auctions/{id}/end-time-request  {requested_end_time, reason}
 *   GET   /api/auctions/{id}/end-time-request
 *   GET   /api/auctions/{id}/edited-history
 *
 * Bilingual labels via i18n prop.  All errors surface as sonner toasts.
 */
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import {
  Loader2, Save, Image as ImageIcon, Calendar, Truck,
  Plus, Clock, History, Check, X,
} from 'lucide-react';
import API_BASE from '../config';

const API = API_BASE;

// ─────────────────────────────────────────────────────────────────────
//  Utility — bilingual label
// ─────────────────────────────────────────────────────────────────────

function useBilingual() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  return {
    fr,
    L: fr
      ? {
          title:               'Modifier l\u2019enchère',
          info:                'Informations',
          media:               'Médias',
          schedule:            'Calendrier & Ramassage',
          shipping:            'Expédition',
          addLot:              'Ajouter un lot',
          endTime:             'Heure de fin',
          history:             'Historique',
          saveInfo:            'Enregistrer les informations',
          saveSchedule:        'Enregistrer le calendrier',
          saveShipping:        'Enregistrer l\u2019expédition',
          savedOk:             'Enregistré',
          saveFailed:          'Échec de l\u2019enregistrement',
          fieldTitle:          'Titre',
          fieldDescription:    'Description',
          previewDate:         'Date d\u2019aperçu',
          previewTime:         'Heure d\u2019aperçu',
          pickupLocation:      'Lieu de ramassage',
          pickupWindowStart:   'Début de la fenêtre de ramassage',
          pickupWindowEnd:     'Fin de la fenêtre de ramassage',
          pickupInstructions:  'Instructions de ramassage',
          shippingAvailable:   'Expédition disponible',
          shippingNotes:       'Notes d\u2019expédition',
          shippingEstimate:    'Coût estimé (info seulement)',
          shippingEstimateHelp:'Ceci est une estimation. Aucun paiement Stripe n\u2019est prélevé.',
          carrier:             'Transporteur',
          addImage:            'Ajouter des images',
          uploadHint:          'Colle une URL d\u2019image et appuie sur Ajouter',
          currentImages:       'Images actuelles',
          removeOwnOnly:       'Vous ne pouvez retirer que les images que vous avez ajoutées.',
          reorder:             'Réordonner',
          newLotTitle:         'Titre du nouveau lot',
          newLotDescription:   'Description',
          newLotQuantity:      'Quantité',
          newLotStartPrice:    'Mise de départ',
          newLotCategory:      'Catégorie',
          newLotCondition:     'État',
          submitNewLot:        'Soumettre pour approbation',
          newLotPending:       'Nouveau lot ajouté — en attente de révision admin.',
          endTimeCurrent:      'Heure de fin actuelle',
          endTimeRequestBtn:   'Demander un changement d\u2019heure de fin',
          endTimeRequestedNew: 'Nouvelle heure de fin demandée',
          endTimeReason:       'Motif (minimum 20 caractères)',
          endTimeSubmit:       'Envoyer la demande',
          endTimePending:      'Demande en attente',
          endTimeApproved:     'Demande approuvée',
          endTimeDenied:       'Demande refusée',
          adminNoteLabel:      'Note de l\u2019administrateur',
          historyEmpty:        'Aucune modification enregistrée pour cette enchère.',
          close:               'Fermer',
        }
      : {
          title:               'Edit Auction',
          info:                'Info',
          media:               'Media',
          schedule:            'Schedule & Pickup',
          shipping:            'Shipping',
          addLot:              'Add Lot',
          endTime:             'End Time',
          history:             'History',
          saveInfo:            'Save info',
          saveSchedule:        'Save schedule',
          saveShipping:        'Save shipping',
          savedOk:             'Saved',
          saveFailed:          'Save failed',
          fieldTitle:          'Title',
          fieldDescription:    'Description',
          previewDate:         'Preview date',
          previewTime:         'Preview time',
          pickupLocation:      'Pickup location',
          pickupWindowStart:   'Pickup window start',
          pickupWindowEnd:     'Pickup window end',
          pickupInstructions:  'Pickup instructions',
          shippingAvailable:   'Shipping available',
          shippingNotes:       'Shipping notes',
          shippingEstimate:    'Estimated cost (info only)',
          shippingEstimateHelp:'This is an estimate. No Stripe payment is charged.',
          carrier:             'Carrier',
          addImage:            'Add image',
          uploadHint:          'Paste an image URL and press Add',
          currentImages:       'Current images',
          removeOwnOnly:       'You can only remove images you added.',
          reorder:             'Reorder',
          newLotTitle:         'New lot title',
          newLotDescription:   'Description',
          newLotQuantity:      'Quantity',
          newLotStartPrice:    'Starting price',
          newLotCategory:      'Category',
          newLotCondition:     'Condition',
          submitNewLot:        'Submit for review',
          newLotPending:       'New lot added — pending admin review.',
          endTimeCurrent:      'Current end time',
          endTimeRequestBtn:   'Request end-time change',
          endTimeRequestedNew: 'Requested new end time',
          endTimeReason:       'Reason (min 20 chars)',
          endTimeSubmit:       'Submit request',
          endTimePending:      'Request pending',
          endTimeApproved:     'Request approved',
          endTimeDenied:       'Request denied',
          adminNoteLabel:      'Admin note',
          historyEmpty:        'No edits recorded for this auction yet.',
          close:               'Close',
        },
  };
}


// ─────────────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────────────

export default function SellerLiveEditModal({
  open, onClose, listing, token, onSaved,
}) {
  const { L, fr } = useBilingual();
  const auctionId = listing?.id;

  const headers = { Authorization: `Bearer ${token}` };

  // ── Field states ────────────────────────────────────────────────
  const [title, setTitle] = useState(listing?.title || '');
  const [description, setDescription] = useState(listing?.description || '');
  const [savingInfo, setSavingInfo] = useState(false);

  const [images, setImages] = useState(listing?.images || listing?.photos || []);
  const [newImageUrl, setNewImageUrl] = useState('');

  const [schedule, setSchedule] = useState(listing?.schedule || {});
  const [pickup, setPickup] = useState(listing?.pickup || {});
  const [savingSchedule, setSavingSchedule] = useState(false);

  const [shipping, setShipping] = useState(listing?.shipping || {});
  const [savingShipping, setSavingShipping] = useState(false);

  const [newLot, setNewLot] = useState({
    title: '', description: '', quantity: 1, starting_price: '',
    category: 'other', condition: 'good',
  });
  const [submittingLot, setSubmittingLot] = useState(false);

  const [endTimeReq, setEndTimeReq] = useState(null);
  const [newEndTime, setNewEndTime] = useState('');
  const [endTimeReason, setEndTimeReason] = useState('');
  const [submittingEndTime, setSubmittingEndTime] = useState(false);

  const [history, setHistory] = useState([]);

  // ── Load current end-time request + history on open ────────────
  useEffect(() => {
    if (!open || !auctionId) return;
    (async () => {
      try {
        const [er, hr] = await Promise.all([
          axios.get(`${API}/auctions/${auctionId}/end-time-request`, { headers }),
          axios.get(`${API}/auctions/${auctionId}/edited-history`, { headers }),
        ]);
        setEndTimeReq(er.data || null);
        setHistory(hr.data?.history || []);
      } catch (_) { /* soft */ }
    })();
  }, [open, auctionId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      toast.error(e.response?.data?.detail || L.saveFailed);
      throw e;
    }
  }, [auctionId, headers, L, onSaved]);

  const saveInfo = async () => {
    setSavingInfo(true);
    try {
      if (title !== listing?.title) await patchField('title', title);
      if (description !== listing?.description) await patchField('description', description);
    } finally {
      setSavingInfo(false);
    }
  };

  const addImage = async () => {
    if (!newImageUrl.trim()) return;
    try {
      const r = await patchField('images', { add: [newImageUrl.trim()] });
      setImages(r.new_value);
      setNewImageUrl('');
    } catch (_) { /* toast already shown by patchField */ }
  };
  const removeImage = async (url) => {
    try {
      const r = await patchField('images', { remove: [url] });
      setImages(r.new_value);
    } catch (_) { /* toast already shown */ }
  };

  const saveSchedule = async () => {
    setSavingSchedule(true);
    try {
      await patchField('schedule', schedule);
      await patchField('pickup', pickup);
    } finally {
      setSavingSchedule(false);
    }
  };
  const saveShipping = async () => {
    setSavingShipping(true);
    try { await patchField('shipping', shipping); }
    finally { setSavingShipping(false); }
  };

  const submitNewLot = async () => {
    setSubmittingLot(true);
    try {
      await axios.post(`${API}/auctions/${auctionId}/lots`,
        { lot: newLot }, { headers });
      toast.success(L.newLotPending);
      setNewLot({ title: '', description: '', quantity: 1,
                  starting_price: '', category: 'other', condition: 'good' });
    } catch (e) {
      toast.error(e.response?.data?.detail || L.saveFailed);
    } finally {
      setSubmittingLot(false);
    }
  };

  const submitEndTimeRequest = async () => {
    if (!newEndTime) return toast.error(L.saveFailed);
    if ((endTimeReason || '').trim().length < 20) return toast.error(L.endTimeReason);
    setSubmittingEndTime(true);
    try {
      const iso = new Date(newEndTime).toISOString();
      const r = await axios.post(
        `${API}/auctions/${auctionId}/end-time-request`,
        { requested_end_time: iso, reason: endTimeReason.trim() },
        { headers });
      setEndTimeReq(r.data);
      toast.success(L.endTimePending);
      setEndTimeReason('');
    } catch (e) {
      toast.error(e.response?.data?.detail || L.saveFailed);
    } finally {
      setSubmittingEndTime(false);
    }
  };

  const requestStatusBadge = (st) => {
    if (!st) return null;
    const map = {
      pending:  <Badge className="bg-amber-100 text-amber-800 border-amber-300">{L.endTimePending}</Badge>,
      approved: <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300"><Check className="h-3 w-3 mr-1 inline" />{L.endTimeApproved}</Badge>,
      denied:   <Badge className="bg-rose-100 text-rose-800 border-rose-300"><X className="h-3 w-3 mr-1 inline" />{L.endTimeDenied}</Badge>,
    };
    return map[st] || null;
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="seller-live-edit-modal">
        <DialogHeader>
          <DialogTitle className="text-2xl">{L.title}</DialogTitle>
          <DialogDescription>{listing?.title}</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="info" className="mt-4">
          <TabsList className="grid grid-cols-7 h-auto">
            <TabsTrigger value="info"     data-testid="edit-tab-info">{L.info}</TabsTrigger>
            <TabsTrigger value="media"    data-testid="edit-tab-media">{L.media}</TabsTrigger>
            <TabsTrigger value="schedule" data-testid="edit-tab-schedule">{L.schedule}</TabsTrigger>
            <TabsTrigger value="shipping" data-testid="edit-tab-shipping">{L.shipping}</TabsTrigger>
            <TabsTrigger value="add-lot"  data-testid="edit-tab-add-lot">{L.addLot}</TabsTrigger>
            <TabsTrigger value="end-time" data-testid="edit-tab-end-time">{L.endTime}</TabsTrigger>
            <TabsTrigger value="history"  data-testid="edit-tab-history">{L.history}</TabsTrigger>
          </TabsList>

          {/* Section A — Info */}
          <TabsContent value="info" className="space-y-4 pt-4">
            <div>
              <Label>{L.fieldTitle}</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)}
                data-testid="edit-title-input" />
            </div>
            <div>
              <Label>{L.fieldDescription}</Label>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)}
                rows={6} data-testid="edit-description-input" />
            </div>
            <Button onClick={saveInfo} disabled={savingInfo}
              data-testid="save-info-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white">
              {savingInfo ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {L.saveInfo}
            </Button>
          </TabsContent>

          {/* Section B — Media */}
          <TabsContent value="media" className="space-y-4 pt-4">
            <p className="text-xs text-slate-500">{L.removeOwnOnly}</p>
            <div className="flex gap-2">
              <Input value={newImageUrl} onChange={(e) => setNewImageUrl(e.target.value)}
                placeholder={L.uploadHint} data-testid="new-image-url-input" />
              <Button onClick={addImage} data-testid="add-image-btn">
                <ImageIcon className="h-4 w-4 mr-2" /> {L.addImage}
              </Button>
            </div>
            <div>
              <Label>{L.currentImages} ({images.length})</Label>
              <div className="grid grid-cols-3 gap-3 mt-2">
                {images.map((url, i) => (
                  <div key={`${url}-${i}`} className="relative group">
                    <img src={typeof url === 'string' ? url : url?.url}
                      alt="" className="w-full h-24 object-cover rounded" />
                    <Button size="sm" variant="destructive"
                      onClick={() => removeImage(typeof url === 'string' ? url : url?.url)}
                      className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition h-6 w-6 p-0"
                      data-testid={`remove-image-btn-${i}`}>
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          {/* Section C — Schedule & Pickup */}
          <TabsContent value="schedule" className="space-y-4 pt-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{L.previewDate}</Label>
                <Input type="date" value={schedule.preview_date || ''}
                  onChange={(e) => setSchedule({ ...schedule, preview_date: e.target.value })} />
              </div>
              <div>
                <Label>{L.previewTime}</Label>
                <Input type="time" value={schedule.preview_time || ''}
                  onChange={(e) => setSchedule({ ...schedule, preview_time: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>{L.pickupLocation}</Label>
              <Input value={pickup.location || ''}
                onChange={(e) => setPickup({ ...pickup, location: e.target.value })}
                data-testid="pickup-location-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{L.pickupWindowStart}</Label>
                <Input type="datetime-local" value={pickup.window_start || ''}
                  onChange={(e) => setPickup({ ...pickup, window_start: e.target.value })} />
              </div>
              <div>
                <Label>{L.pickupWindowEnd}</Label>
                <Input type="datetime-local" value={pickup.window_end || ''}
                  onChange={(e) => setPickup({ ...pickup, window_end: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>{L.pickupInstructions}</Label>
              <Textarea value={pickup.instructions || ''}
                onChange={(e) => setPickup({ ...pickup, instructions: e.target.value })}
                rows={3} data-testid="pickup-instructions-input" />
            </div>
            <Button onClick={saveSchedule} disabled={savingSchedule}
              data-testid="save-schedule-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white">
              {savingSchedule ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Calendar className="h-4 w-4 mr-2" />}
              {L.saveSchedule}
            </Button>
          </TabsContent>

          {/* Section D — Shipping */}
          <TabsContent value="shipping" className="space-y-4 pt-4">
            <div className="flex items-center gap-3">
              <input type="checkbox" checked={!!shipping.available}
                onChange={(e) => setShipping({ ...shipping, available: e.target.checked })}
                data-testid="shipping-available-toggle" />
              <Label>{L.shippingAvailable}</Label>
            </div>
            <div>
              <Label>{L.carrier}</Label>
              <Input value={shipping.carrier || ''}
                onChange={(e) => setShipping({ ...shipping, carrier: e.target.value })} />
            </div>
            <div>
              <Label>{L.shippingNotes}</Label>
              <Textarea value={shipping.notes || ''}
                onChange={(e) => setShipping({ ...shipping, notes: e.target.value })}
                rows={3} data-testid="shipping-notes-input" />
            </div>
            <div>
              <Label>{L.shippingEstimate}</Label>
              <Input value={shipping.estimated_cost || ''}
                onChange={(e) => setShipping({ ...shipping, estimated_cost: e.target.value })}
                placeholder="45.00" data-testid="shipping-estimate-input" />
              <p className="text-xs text-slate-500 mt-1 italic">{L.shippingEstimateHelp}</p>
            </div>
            <Button onClick={saveShipping} disabled={savingShipping}
              data-testid="save-shipping-btn"
              className="bg-blue-600 hover:bg-blue-700 text-white">
              {savingShipping ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Truck className="h-4 w-4 mr-2" />}
              {L.saveShipping}
            </Button>
          </TabsContent>

          {/* Section E — Add Lot */}
          <TabsContent value="add-lot" className="space-y-3 pt-4">
            <div>
              <Label>{L.newLotTitle}</Label>
              <Input value={newLot.title}
                onChange={(e) => setNewLot({ ...newLot, title: e.target.value })}
                data-testid="new-lot-title" />
            </div>
            <div>
              <Label>{L.newLotDescription}</Label>
              <Textarea rows={3} value={newLot.description}
                onChange={(e) => setNewLot({ ...newLot, description: e.target.value })} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>{L.newLotQuantity}</Label>
                <Input type="number" min={1} value={newLot.quantity}
                  onChange={(e) => setNewLot({ ...newLot, quantity: Number(e.target.value) || 1 })} />
              </div>
              <div>
                <Label>{L.newLotStartPrice}</Label>
                <Input type="number" step="0.01" min={0} value={newLot.starting_price}
                  onChange={(e) => setNewLot({ ...newLot, starting_price: Number(e.target.value) || 0 })} />
              </div>
              <div>
                <Label>{L.newLotCondition}</Label>
                <Input value={newLot.condition}
                  onChange={(e) => setNewLot({ ...newLot, condition: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>{L.newLotCategory}</Label>
              <Input value={newLot.category}
                onChange={(e) => setNewLot({ ...newLot, category: e.target.value })} />
            </div>
            <Button onClick={submitNewLot} disabled={submittingLot || !newLot.title.trim()}
              data-testid="submit-new-lot-btn"
              className="bg-cyan-600 hover:bg-cyan-700 text-white">
              {submittingLot ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              {L.submitNewLot}
            </Button>
            <p className="text-xs text-amber-700 italic">{L.newLotPending}</p>
          </TabsContent>

          {/* Section F — End Time */}
          <TabsContent value="end-time" className="space-y-3 pt-4">
            <div className="text-sm">
              <Label>{L.endTimeCurrent}</Label>
              <p className="mt-1 font-mono text-slate-700 dark:text-slate-300">
                {listing?.auction_end_date || listing?.end_time || '—'}
              </p>
            </div>
            {endTimeReq ? (
              <div className="p-3 rounded-lg border bg-slate-50 dark:bg-slate-800 space-y-2">
                <div className="flex items-center gap-2">
                  {requestStatusBadge(endTimeReq.status)}
                </div>
                <div className="text-sm">
                  <strong>{L.endTimeRequestedNew}:</strong>{' '}
                  <span className="font-mono">{endTimeReq.requested_end_time}</span>
                </div>
                <div className="text-sm">
                  <strong>{L.endTimeReason}:</strong> {endTimeReq.reason}
                </div>
                {endTimeReq.admin_note && (
                  <div className="text-sm">
                    <strong>{L.adminNoteLabel}:</strong> {endTimeReq.admin_note}
                  </div>
                )}
                {endTimeReq.status === 'pending' && (
                  <p className="text-xs text-amber-700 italic mt-2">
                    {fr
                      ? 'Vous ne pouvez soumettre qu\u2019une seule demande à la fois.'
                      : 'Only one pending request allowed per auction.'}
                  </p>
                )}
              </div>
            ) : null}
            {(!endTimeReq || endTimeReq.status !== 'pending') && (
              <>
                <div>
                  <Label>{L.endTimeRequestedNew}</Label>
                  <Input type="datetime-local"
                    value={newEndTime}
                    onChange={(e) => setNewEndTime(e.target.value)}
                    data-testid="new-end-time-input" />
                </div>
                <div>
                  <Label>{L.endTimeReason}</Label>
                  <Textarea rows={3} value={endTimeReason}
                    onChange={(e) => setEndTimeReason(e.target.value)}
                    data-testid="end-time-reason-input" />
                </div>
                <Button onClick={submitEndTimeRequest}
                  disabled={submittingEndTime || endTimeReason.trim().length < 20}
                  data-testid="submit-end-time-request-btn"
                  className="bg-amber-600 hover:bg-amber-700 text-white">
                  {submittingEndTime ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Clock className="h-4 w-4 mr-2" />}
                  {L.endTimeSubmit}
                </Button>
              </>
            )}
          </TabsContent>

          {/* History */}
          <TabsContent value="history" className="pt-4" data-testid="edit-history-panel">
            {history.length === 0 ? (
              <p className="text-sm text-slate-500 italic">{L.historyEmpty}</p>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {history.slice().reverse().map((h, i) => (
                  <div key={h.id || i} className="p-3 rounded-lg border bg-slate-50 dark:bg-slate-800 text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="outline"><History className="h-3 w-3 mr-1 inline" />{h.field}</Badge>
                      <span className="text-slate-500 font-mono">{h.edited_at}</span>
                    </div>
                    <details>
                      <summary className="cursor-pointer text-slate-600 hover:underline">
                        {fr ? 'Voir la modification' : 'View change'}
                      </summary>
                      <div className="mt-2 space-y-1 font-mono text-[11px]">
                        <div><span className="text-rose-600">- </span>{JSON.stringify(h.old_value)}</div>
                        <div><span className="text-emerald-600">+ </span>{JSON.stringify(h.new_value)}</div>
                        <div className="text-slate-500">{fr ? 'Par' : 'By'}: {h.edited_by}</div>
                      </div>
                    </details>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose} data-testid="close-edit-modal">{L.close}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
