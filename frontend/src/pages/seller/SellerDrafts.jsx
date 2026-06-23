/**
 * iter313 D4 — Unified Drafts dashboard sub-tab.
 *
 * Aggregates drafts across all 5 listing types:
 *   • Marketplace
 *   • Lots / Multi-Item
 *   • Storage Auction
 *   • Vehicle (single)
 *   • Multi-Lot Vehicle
 *
 * Plus draft_expired rows within the 60-day restore window (P1).
 *
 * Endpoints used:
 *   GET    /api/drafts                  -> list
 *   POST   /api/drafts/{id}/restore     -> restore expired draft
 *   DELETE /api/drafts/{id}             -> permanent delete
 *
 * "Edit" navigates to the correct create-wizard URL with ?draft_id=X
 * so the wizard hydrates its formData from the draft payload.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPE_TO_WIZARD = {
  marketplace:       (id) => `/create-listing?draft_id=${id}`,
  lots:              (id) => `/create-multi-item-listing?draft_id=${id}`,
  storage:           (id) => `/storage-auctions/create?draft_id=${id}`,
  vehicle:           (id) => `/vehicle-auctions/create?draft_id=${id}`,
  multi_lot_vehicle: (id) => `/vehicle-auctions/multi-lot/create?draft_id=${id}`,
};

const SellerDrafts = () => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/drafts?include_expired=true`);
      setDrafts(Array.isArray(r.data?.drafts) ? r.data.drafts : []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load drafts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleEdit = (d) => {
    const builder = TYPE_TO_WIZARD[d.type];
    if (!builder) return toast.error('Unknown listing type');
    navigate(builder(d.id));
  };

  const handleDelete = async (d) => {
    if (!window.confirm(fr ? 'Supprimer ce brouillon ?' : 'Delete this draft?')) return;
    try {
      await axios.delete(`${API}/drafts/${d.id}`);
      toast.success(fr ? 'Brouillon supprimé' : 'Draft deleted');
      refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Delete failed');
    }
  };

  const handleRestore = async (d) => {
    try {
      await axios.post(`${API}/drafts/${d.id}/restore`);
      toast.success(fr ? 'Brouillon restauré' : 'Draft restored');
      refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail?.message_en || err?.response?.data?.detail || 'Restore failed');
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground" data-testid="seller-drafts-loading">{fr ? 'Chargement…' : 'Loading…'}</div>;
  }

  if (drafts.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground" data-testid="seller-drafts-empty">
        {fr ? 'Aucun brouillon enregistré pour le moment.' : 'No saved drafts yet.'}
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="seller-drafts-tab">
      {drafts.map((d) => {
        const isExpired = d.status === 'draft_expired';
        const expSoon = !isExpired && typeof d.expires_in_days === 'number' && d.expires_in_days <= 7;
        return (
          <Card key={d.id} className="p-4" data-testid={`draft-card-${d.id}`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <Badge variant="outline" className="text-xs">
                    {fr ? d.type_label?.fr : d.type_label?.en}
                  </Badge>
                  {isExpired ? (
                    <Badge className="bg-rose-100 text-rose-700">
                      {fr ? `Expiré (restaurer dans ${d.restore_days_left}j)` : `Expired (restore in ${d.restore_days_left}d)`}
                    </Badge>
                  ) : expSoon ? (
                    <Badge className="bg-amber-100 text-amber-800" data-testid={`draft-expiry-warn-${d.id}`}>
                      {fr ? `Expire dans ${d.expires_in_days}j` : `Expires in ${d.expires_in_days}d`}
                    </Badge>
                  ) : (
                    <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {fr ? `${d.expires_in_days}j restants` : `${d.expires_in_days}d left`}
                    </Badge>
                  )}
                </div>
                <h3 className="font-semibold truncate" data-testid={`draft-title-${d.id}`}>{d.title}</h3>
                <p className="text-xs text-muted-foreground">
                  {fr ? 'Modifié' : 'Updated'}: {d.updated_at ? new Date(d.updated_at).toLocaleString() : '—'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {isExpired ? (
                  <Button
                    size="sm"
                    onClick={() => handleRestore(d)}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    data-testid={`restore-draft-${d.id}`}
                  >
                    {fr ? 'Restaurer' : 'Restore'}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => handleEdit(d)}
                    data-testid={`edit-draft-${d.id}`}
                  >
                    {fr ? 'Reprendre' : 'Resume'}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleDelete(d)}
                  className="text-red-700 border-red-200 hover:bg-red-50"
                  data-testid={`delete-draft-${d.id}`}
                >
                  {fr ? 'Supprimer' : 'Delete'}
                </Button>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
};

export default SellerDrafts;
