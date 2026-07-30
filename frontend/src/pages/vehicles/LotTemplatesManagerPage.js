/**
 * LotTemplatesManagerPage — iter304
 *
 * Dealer-only tab for managing saved lot templates (used by the multi-lot
 * vehicle auction wizard). Bilingual EN/FR.
 *
 * Route: /vehicle-auctions/lot-templates
 * Shows: list of templates with name, fields preview (Make/Model/etc.),
 *        Edit (rename) and Delete actions. Max 20 templates per dealer.
 */
import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import {
  BookmarkPlus, Edit3, Trash2, ArrowLeft, Loader2, Save, X, FolderOpen, Plus,
} from 'lucide-react';

const API = API_BASE;

const LotTemplatesManagerPage = () => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const L = (en, frTxt) => (fr ? frTxt : en);

  const [items, setItems] = useState([]);
  const [maxN, setMaxN] = useState(20);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API}/lot-templates`, { headers: { Authorization: `Bearer ${token}` } });
      setItems(r.data?.items || []);
      setMaxN(r.data?.max || 20);
    } catch (err) {
      toast.error(L('Failed to load templates', 'Échec du chargement'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleDelete = async (id, name) => {
    if (!window.confirm(L(`Delete template "${name}"?`, `Supprimer le modèle « ${name} » ?`))) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/lot-templates/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(L('Template deleted', 'Modèle supprimé'));
      fetchAll();
    } catch (err) {
      toast.error(L('Failed to delete', 'Échec de la suppression'));
    }
  };

  const startEdit = (id, name) => { setEditingId(id); setEditingName(name); };
  const cancelEdit = () => { setEditingId(null); setEditingName(''); };
  const saveEdit = async () => {
    if (!editingName.trim()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${API}/lot-templates/${editingId}`, { name: editingName.trim() },
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success(L('Template updated', 'Modèle mis à jour'));
      cancelEdit();
      fetchAll();
    } catch (err) {
      toast.error(L('Failed to update', 'Échec de la mise à jour'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="lot-templates-manager-page">
      <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/vehicle-dashboard')}
            className="text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 mb-3 inline-flex items-center"
            data-testid="back-to-listings-btn"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            {L('Back to My Vehicle Listings', 'Retour à mes annonces')}
          </button>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2">
                <FolderOpen className="h-7 w-7 text-blue-600" />
                {L('Lot Templates', 'Modèles de lots')}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                {L(
                  'Reusable presets that pre-fill the multi-lot wizard. Speed up creating similar lots.',
                  "Présélections réutilisables qui pré-remplissent l'assistant multi-lots. Accélérez la création de lots similaires.",
                )}
              </p>
            </div>
            <Badge variant="outline" className="self-start whitespace-nowrap" data-testid="templates-count-badge">
              {items.length} / {maxN}
            </Badge>
          </div>
        </div>

        {items.length === 0 ? (
          <Card className="p-10 text-center">
            <BookmarkPlus className="h-12 w-12 mx-auto text-slate-300 mb-3" />
            <h3 className="text-lg font-semibold mb-1">
              {L('No templates yet', 'Aucun modèle pour le moment')}
            </h3>
            <p className="text-sm text-slate-500 mb-5 max-w-md mx-auto">
              {L(
                "Save a template from the Multi-Lot Vehicle Auction wizard (Step 5 — Auction Settings) to reuse common fields across lots.",
                "Enregistrez un modèle depuis l'assistant Enchère multi-lots (étape 5 — Paramètres de la vente) pour réutiliser les champs communs.",
              )}
            </p>
            <Button onClick={() => navigate('/vehicle-multi-lot/create')} data-testid="go-to-multi-lot-btn">
              <Plus className="h-4 w-4 mr-1" /> {L('Create a Multi-Lot Auction', 'Créer une enchère multi-lots')}
            </Button>
          </Card>
        ) : (
          <div className="space-y-3" data-testid="templates-list">
            {items.map((tpl) => {
              const f = tpl.fields || {};
              const previewBits = [];
              if (f.make || f.model) previewBits.push(`${f.make || ''} ${f.model || ''}`.trim());
              if (f.body_type) previewBits.push(f.body_type);
              if (f.transmission) previewBits.push(f.transmission);
              if (f.fuel_type) previewBits.push(f.fuel_type);
              if (f.starting_price) previewBits.push(`$${Number(f.starting_price).toLocaleString()}`);
              if (f.location_province) previewBits.push(f.location_province);
              return (
                <Card key={tpl.id} className="p-4" data-testid={`template-row-${tpl.id}`}>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      {editingId === tpl.id ? (
                        <div className="flex gap-2 items-center">
                          <Input
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            maxLength={60}
                            className="flex-1"
                            data-testid={`template-edit-input-${tpl.id}`}
                            autoFocus
                          />
                          <Button size="sm" onClick={saveEdit} disabled={saving} data-testid={`template-save-edit-${tpl.id}`}>
                            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={cancelEdit} disabled={saving} data-testid={`template-cancel-edit-${tpl.id}`}>
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <>
                          <h3 className="font-semibold text-base truncate" data-testid={`template-name-${tpl.id}`}>{tpl.name}</h3>
                          <p className="text-xs text-slate-500 mt-1 line-clamp-1">
                            {previewBits.join(' · ') || L('No preview', 'Aucun aperçu')}
                          </p>
                        </>
                      )}
                    </div>
                    {editingId !== tpl.id && (
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => startEdit(tpl.id, tpl.name)} data-testid={`template-edit-btn-${tpl.id}`}>
                          <Edit3 className="h-3.5 w-3.5 mr-1" /> {L('Edit', 'Modifier')}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => handleDelete(tpl.id, tpl.name)} className="text-rose-600 hover:bg-rose-50" data-testid={`template-delete-btn-${tpl.id}`}>
                          <Trash2 className="h-3.5 w-3.5 mr-1" /> {L('Delete', 'Supprimer')}
                        </Button>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default LotTemplatesManagerPage;
