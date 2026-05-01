import API_BASE from '../../config';
import React, { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { ShieldCheck, Loader2 } from 'lucide-react';

const API = API_BASE;
const PROVINCES = ['AB','BC','MB','NB','NL','NS','ON','PE','QC','SK','NT','NU','YT'];

const StorageFacilityRegister = () => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const isFr = (i18n.language || '').startsWith('fr');

  const [form, setForm] = useState({
    company_name: '', company_name_fr: '', contact_name: '',
    email: '', phone: '', address: '', city: '', province: 'QC',
    postal_code: '', units_available: 0, referral_source: '', accepted_terms: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!token) { toast.error(isFr ? 'Connectez-vous d\'abord' : 'Sign in first'); return; }
    if (!form.accepted_terms) { toast.error(isFr ? 'Acceptez les conditions' : 'Accept the terms'); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/storage-facilities/register`, form, { headers: { Authorization: `Bearer ${token}` } });
      setSubmitted(true);
    } catch (err) {
      toast.error(err?.response?.data?.detail || (isFr ? 'Échec de l\'inscription' : 'Registration failed'));
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Card className="max-w-md p-8 text-center" data-testid="register-success">
          <ShieldCheck className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
          <h2 className="text-2xl font-bold mb-2">{isFr ? 'Demande reçue' : 'Application received'}</h2>
          <p className="text-sm text-muted-foreground mb-6">
            {isFr
              ? 'Votre demande est en cours d\'examen. Vous recevrez un courriel de confirmation dans 1 à 2 jours ouvrables une fois votre compte vérifié.'
              : 'Your application is under review. You\'ll receive a confirmation email within 1–2 business days once your account is verified.'}
          </p>
          <Button onClick={() => navigate('/storage-auctions')}>{isFr ? "Retour aux enchères" : 'Back to auctions'}</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-register-page">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold mb-2">{isFr ? 'Lister votre facilité' : 'List Your Facility'}</h1>
        <p className="text-sm text-muted-foreground mb-2">{isFr ? 'Inscription pour facilités d\'entreposage canadiennes' : 'Registration for Canadian storage facilities'}</p>
        <p className="text-xs text-emerald-700 dark:text-emerald-400 mb-6">
          ✅ {isFr ? 'Commission de 5% seulement — aucuns frais acheteur — pas d\'abonnement mensuel.' : '5% commission only — no buyer fees — no monthly subscription.'}
        </p>

        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Nom de l\'entreprise (EN)' : 'Company Name (EN)'} *</Label>
                <Input required value={form.company_name} onChange={e => set('company_name', e.target.value)} data-testid="reg-company-name" />
              </div>
              <div>
                <Label>{isFr ? 'Nom en français (optionnel)' : 'Company Name (FR — optional)'}</Label>
                <Input value={form.company_name_fr} onChange={e => set('company_name_fr', e.target.value)} />
              </div>
            </div>

            <div>
              <Label>{isFr ? 'Nom du contact' : 'Contact Name'} *</Label>
              <Input required value={form.contact_name} onChange={e => set('contact_name', e.target.value)} data-testid="reg-contact-name" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Courriel' : 'Email'} *</Label>
                <Input type="email" required value={form.email} onChange={e => set('email', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Téléphone' : 'Phone'} *</Label>
                <Input required value={form.phone} onChange={e => set('phone', e.target.value)} />
              </div>
            </div>

            <div>
              <Label>{isFr ? 'Adresse' : 'Address'} *</Label>
              <Input required value={form.address} onChange={e => set('address', e.target.value)} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <Label>{isFr ? 'Ville' : 'City'} *</Label>
                <Input required value={form.city} onChange={e => set('city', e.target.value)} />
              </div>
              <div>
                <Label>{isFr ? 'Province' : 'Province'} *</Label>
                <Select value={form.province} onValueChange={v => set('province', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PROVINCES.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>{isFr ? 'Code postal' : 'Postal Code'} *</Label>
                <Input required value={form.postal_code} onChange={e => set('postal_code', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>{isFr ? 'Unités disponibles' : 'Units Available'}</Label>
                <Input type="number" min="0" value={form.units_available} onChange={e => set('units_available', parseInt(e.target.value || '0'))} />
              </div>
              <div>
                <Label>{isFr ? 'Comment avez-vous entendu parler ?' : 'How did you hear about us?'}</Label>
                <Input value={form.referral_source} onChange={e => set('referral_source', e.target.value)} />
              </div>
            </div>

            <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
              <Checkbox checked={form.accepted_terms} onCheckedChange={v => set('accepted_terms', v === true)} className="mt-0.5" data-testid="reg-accept-terms" />
              <label className="text-xs leading-snug">
                {isFr
                  ? <>J'accepte les <a href="/storage-auctions/terms" target="_blank" rel="noreferrer" className="underline text-blue-600">conditions générales</a> des enchères d'entreposage BidVex et reconnais que ma facilité est seule responsable du respect des lois provinciales sur les droits de rétention.</>
                  : <>I accept the BidVex Storage Auction <a href="/storage-auctions/terms" target="_blank" rel="noreferrer" className="underline text-blue-600">Terms & Conditions</a> and acknowledge that my facility is solely responsible for compliance with provincial lien laws.</>}
              </label>
            </div>

            <Button type="submit" disabled={submitting} className="w-full bg-blue-600 hover:bg-blue-700 text-white" data-testid="reg-submit-btn">
              {submitting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
              {isFr ? 'Soumettre' : 'Submit'}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default StorageFacilityRegister;
