import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import API_BASE from '../config';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Briefcase, Loader2, CheckCircle } from 'lucide-react';
import SEO from '../components/SEO';

/**
 * iter342 — General career application form (/careers/apply).
 * Minimal: Name, Email, Phone, Position (dropdown of open roles +
 * "General Application"), Message. Triggers careers@bidvex.com admin
 * alert + bilingual applicant confirmation.
 */
export default function CareersApplyPage() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [jobs, setJobs] = useState([]);
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', phone: '', position: '', message: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/careers/jobs`);
        setJobs(Array.isArray(r.data?.jobs) ? r.data.jobs : (Array.isArray(r.data) ? r.data : []));
      } catch { /* jobs are optional — General Application always available */ }
    })();
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.first_name || !form.last_name || !form.email || !form.phone || !form.position) {
      toast.error(fr ? 'Veuillez remplir tous les champs obligatoires.' : 'Please fill all required fields.');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API_BASE}/careers/apply`, { ...form, locale: fr ? 'fr' : 'en' });
      setDone(true);
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error((fr ? d?.message_fr : d?.message_en) || (typeof d === 'string' ? d : null)
        || (fr ? 'Échec de la soumission. Réessayez.' : 'Submission failed. Please retry.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto max-w-2xl py-10 px-4" data-testid="careers-apply-page">
      <SEO
        title={fr ? 'Postuler — Carrières BidVex' : 'Apply — BidVex Careers'}
        description="Apply to join the BidVex team."
        path="/careers/apply"
      />
      <header className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="careers-apply-title">
          <Briefcase className="w-7 h-7 text-blue-600" />
          {fr ? 'Postuler chez BidVex' : 'Apply to BidVex'}
        </h1>
        <p className="text-sm text-slate-500 mt-2">
          {fr
            ? 'Soumettez votre candidature — notre équipe vous contactera dans les 5 à 7 jours ouvrables.'
            : 'Submit your application — our team will be in touch within 5–7 business days.'}
        </p>
      </header>

      {done ? (
        <Card data-testid="careers-apply-success">
          <CardContent className="p-8 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
            <h2 className="text-lg font-semibold mb-2">
              {fr ? 'Candidature reçue !' : 'Application received!'}
            </h2>
            <p className="text-sm text-slate-600">
              {fr
                ? 'Merci pour votre candidature. Un courriel de confirmation vous a été envoyé. Nous vous contacterons dans les 5 à 7 jours ouvrables.'
                : 'Thank you for your application. A confirmation email has been sent to you. We will be in touch within 5–7 business days.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {fr ? 'Formulaire de candidature' : 'Application form'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="apply-first-name">{fr ? 'Prénom *' : 'First name *'}</Label>
                  <Input id="apply-first-name" data-testid="careers-apply-first-name"
                    value={form.first_name} onChange={set('first_name')} required />
                </div>
                <div>
                  <Label htmlFor="apply-last-name">{fr ? 'Nom *' : 'Last name *'}</Label>
                  <Input id="apply-last-name" data-testid="careers-apply-last-name"
                    value={form.last_name} onChange={set('last_name')} required />
                </div>
              </div>
              <div>
                <Label htmlFor="apply-email">{fr ? 'Courriel *' : 'Email *'}</Label>
                <Input id="apply-email" type="email" data-testid="careers-apply-email"
                  value={form.email} onChange={set('email')} required />
              </div>
              <div>
                <Label htmlFor="apply-phone">{fr ? 'Téléphone *' : 'Phone *'}</Label>
                <Input id="apply-phone" type="tel" data-testid="careers-apply-phone"
                  value={form.phone} onChange={set('phone')} required />
              </div>
              <div>
                <Label htmlFor="apply-position">{fr ? 'Poste *' : 'Position *'}</Label>
                <select
                  id="apply-position"
                  data-testid="careers-apply-position"
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                  value={form.position}
                  onChange={set('position')}
                  required
                >
                  <option value="">{fr ? '— Choisir un poste —' : '— Select a position —'}</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={fr ? (j.title_fr || j.title) : j.title}>
                      {fr ? (j.title_fr || j.title) : j.title}
                    </option>
                  ))}
                  <option value={fr ? 'Candidature générale' : 'General Application'}>
                    {fr ? 'Candidature générale' : 'General Application'}
                  </option>
                </select>
              </div>
              <div>
                <Label htmlFor="apply-message">
                  {fr ? 'Message / Lettre de motivation' : 'Message / Cover letter'}
                </Label>
                <Textarea id="apply-message" data-testid="careers-apply-message" rows={5}
                  value={form.message} onChange={set('message')}
                  placeholder={fr ? 'Parlez-nous de vous…' : 'Tell us about yourself…'} />
              </div>
              <Button type="submit" className="w-full h-11" disabled={submitting}
                data-testid="careers-apply-submit-btn">
                {submitting
                  ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />{fr ? 'Envoi…' : 'Submitting…'}</>)
                  : (fr ? 'Soumettre ma candidature' : 'Submit application')}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
