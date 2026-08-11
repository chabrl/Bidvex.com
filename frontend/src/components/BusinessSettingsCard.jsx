/**
 * iter476 — Shared Business Settings / Billing Profile card.
 *
 * Rendered inside a Dialog on the Seller / Partner / Vehicle-Dealer /
 * Storage-Facility dashboards.  Reads/writes `/api/business-settings/me`.
 *
 * Owner-only:  the endpoint scopes every operation to `current_user.id`
 * so a partner cannot edit another partner's billing profile from here.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import API_BASE from '../config';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter, DialogTrigger,
} from './ui/dialog';
import { Building2, Upload, Trash2, Save, Loader2, Image as ImageIcon } from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;
const MAX_LOGO_BYTES = 2 * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'];

const empty = {
  business_name: '', business_address: '', phone: '',
  gst_number: '', qst_number: '', tax_number: '',
  logo_url: '', email: '',
};

/**
 * @param {'seller' | 'partner' | 'dealer' | 'facility'} variant
 * @param {string} triggerLabel — override button label if desired
 */
export const BusinessSettingsCard = ({ variant = 'seller', triggerLabel }) => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [profile, setProfile] = useState(empty);
  const [file, setFile] = useState(null);

  const T = (en, frTxt) => (fr ? frTxt : en);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/business-settings/me`);
      setProfile(r.data || empty);
    } catch (e) {
      toast.error(T('Failed to load profile', 'Échec du chargement'));
    } finally {
      setLoading(false);
    }
  }, [fr]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const save = async () => {
    setSaving(true);
    try {
      const r = await axios.put(`${API}/business-settings/me`, {
        business_name: profile.business_name || '',
        business_address: profile.business_address || '',
        phone: profile.phone || '',
        gst_number: profile.gst_number || '',
        qst_number: profile.qst_number || '',
        tax_number: profile.tax_number || '',
      });
      setProfile(r.data || profile);
      toast.success(T('Billing profile saved', 'Profil de facturation enregistré'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || T('Save failed', 'Échec'));
    } finally {
      setSaving(false);
    }
  };

  const doUpload = async () => {
    if (!file) return;
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error(T('Only PNG, JPG or SVG allowed', 'Seuls PNG, JPG ou SVG sont autorisés'));
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      toast.error(T('Logo must be under 2 MB', 'Le logo doit peser moins de 2 Mo'));
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await axios.post(`${API}/business-settings/me/logo`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setProfile((p) => ({ ...p, logo_url: r.data.logo_url }));
      setFile(null);
      toast.success(T('Logo uploaded', 'Logo téléversé'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || T('Upload failed', 'Échec du téléversement'));
    } finally {
      setUploading(false);
    }
  };

  const removeLogo = async () => {
    if (!profile.logo_url) return;
    try {
      await axios.delete(`${API}/business-settings/me/logo`);
      setProfile((p) => ({ ...p, logo_url: '' }));
      toast.success(T('Logo removed', 'Logo supprimé'));
    } catch (e) {
      toast.error(e?.response?.data?.detail || T('Remove failed', 'Échec'));
    }
  };

  const variantTitle = {
    seller:   T('Business & Billing Profile',       'Profil d\'entreprise et de facturation'),
    partner:  T('Partner Business Profile',         'Profil d\'entreprise partenaire'),
    dealer:   T('Dealer Business Profile',          'Profil du concessionnaire'),
    facility: T('Facility Business Profile',        'Profil de l\'installation'),
  }[variant] || T('Business Profile', 'Profil d\'entreprise');

  const labelBtn = triggerLabel || T('Business & Logo', 'Entreprise et logo');

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          data-testid={`business-settings-open-${variant}`}
        >
          <Building2 className="h-4 w-4" />
          {labelBtn}
        </Button>
      </DialogTrigger>
      <DialogContent
        className="max-w-2xl max-h-[90vh] overflow-y-auto"
        data-testid={`business-settings-dialog-${variant}`}
      >
        <DialogHeader>
          <DialogTitle>{variantTitle}</DialogTitle>
          <DialogDescription>
            {T(
              'These details appear on every buyer / seller PDF (invoices, receipts, statements). Only you can edit them.',
              'Ces informations apparaissent sur chaque PDF acheteur / vendeur (factures, reçus, relevés). Vous êtes seul à pouvoir les modifier.',
            )}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-10 flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            {T('Loading…', 'Chargement…')}
          </div>
        ) : (
          <div className="space-y-4">
            {/* ── Logo ── */}
            <div className="border rounded-lg p-4 space-y-3">
              <div className="flex items-start gap-4">
                <div className="w-32 h-20 border rounded bg-slate-50 dark:bg-slate-800 flex items-center justify-center overflow-hidden">
                  {profile.logo_url ? (
                    <img
                      src={profile.logo_url}
                      alt="Logo"
                      className="max-w-full max-h-full object-contain"
                      data-testid="business-logo-preview"
                    />
                  ) : (
                    <ImageIcon className="h-8 w-8 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 space-y-2">
                  <p className="text-sm font-medium">{T('Business Logo', 'Logo de l\'entreprise')}</p>
                  <p className="text-xs text-muted-foreground">
                    {T('PNG / JPG / SVG · Max 2 MB', 'PNG / JPG / SVG · Max 2 Mo')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <label className="cursor-pointer">
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/svg+xml"
                        className="hidden"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                        data-testid="business-logo-file-input"
                      />
                      <span className="inline-flex items-center gap-1 text-xs px-2 py-1 border rounded-md hover:bg-slate-100 dark:hover:bg-slate-800">
                        <Upload className="h-3 w-3" />
                        {file ? file.name.slice(0, 24) : T('Choose file', 'Choisir un fichier')}
                      </span>
                    </label>
                    <Button
                      size="sm"
                      variant="default"
                      disabled={!file || uploading}
                      onClick={doUpload}
                      className="h-7 text-xs"
                      data-testid="business-logo-upload-btn"
                    >
                      {uploading ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                      ) : (
                        <Upload className="h-3 w-3 mr-1" />
                      )}
                      {T('Upload', 'Téléverser')}
                    </Button>
                    {profile.logo_url && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={removeLogo}
                        className="h-7 text-xs text-red-600"
                        data-testid="business-logo-remove-btn"
                      >
                        <Trash2 className="h-3 w-3 mr-1" />
                        {T('Remove', 'Supprimer')}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* ── Fields ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label htmlFor="bs-name">{T('Business / Legal Name', 'Nom légal / d\'entreprise')}</Label>
                <Input
                  id="bs-name"
                  value={profile.business_name || ''}
                  onChange={(e) => setProfile({ ...profile, business_name: e.target.value })}
                  data-testid="business-name-input"
                />
              </div>
              <div>
                <Label htmlFor="bs-email">{T('Email (read-only)', 'Courriel (lecture)')}</Label>
                <Input
                  id="bs-email"
                  value={profile.email || ''}
                  disabled
                  data-testid="business-email-display"
                />
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="bs-addr">{T('Business Address', 'Adresse d\'entreprise')}</Label>
                <Textarea
                  id="bs-addr"
                  rows={2}
                  value={profile.business_address || ''}
                  onChange={(e) => setProfile({ ...profile, business_address: e.target.value })}
                  data-testid="business-address-input"
                />
              </div>
              <div>
                <Label htmlFor="bs-phone">{T('Phone', 'Téléphone')}</Label>
                <Input
                  id="bs-phone"
                  value={profile.phone || ''}
                  onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                  data-testid="business-phone-input"
                />
              </div>
              <div>
                <Label htmlFor="bs-tax">{T('Generic Tax # (optional)', 'N° fiscal générique (facultatif)')}</Label>
                <Input
                  id="bs-tax"
                  value={profile.tax_number || ''}
                  onChange={(e) => setProfile({ ...profile, tax_number: e.target.value })}
                  data-testid="business-tax-input"
                />
              </div>
              <div>
                <Label htmlFor="bs-gst">{T('GST Number', 'N° TPS')}</Label>
                <Input
                  id="bs-gst"
                  placeholder="123456789RT0001"
                  value={profile.gst_number || ''}
                  onChange={(e) => setProfile({ ...profile, gst_number: e.target.value })}
                  data-testid="business-gst-input"
                />
              </div>
              <div>
                <Label htmlFor="bs-qst">{T('QST Number', 'N° TVQ')}</Label>
                <Input
                  id="bs-qst"
                  placeholder="1234567890TQ0001"
                  value={profile.qst_number || ''}
                  onChange={(e) => setProfile({ ...profile, qst_number: e.target.value })}
                  data-testid="business-qst-input"
                />
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            data-testid="business-settings-cancel"
          >
            {T('Close', 'Fermer')}
          </Button>
          <Button
            onClick={save}
            disabled={saving || loading}
            data-testid="business-settings-save"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
            {T('Save changes', 'Enregistrer')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BusinessSettingsCard;
