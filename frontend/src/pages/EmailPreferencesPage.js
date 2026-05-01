/**
 * EmailPreferencesPage — iter175 (CASL Compliance)
 * =================================================
 * Route: /email-preferences?token=<UUID-signed-token>
 *
 * Bilingual category-level email preferences:
 *   • Marketing & Promotions (toggleable)
 *   • Bidding Alerts          (toggleable)
 *   • Transactional           (mandatory — locked ON per CASL §6(6))
 *
 * Flow:
 *   1. Read `token` from URL ?token=…
 *   2. GET  /api/email-preferences/verify?token=…  → masked email + categories
 *   3. User toggles → POST /api/email-preferences/update
 *
 * Bill 96 / CASL: every visible label, button, status text shows EN + FR.
 */
import API_BASE from '../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useSearchParams, Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import { Loader2, Mail, Lock, ShieldCheck, AlertTriangle, Save, ArrowLeft } from 'lucide-react';

const API = API_BASE;

const EmailPreferencesPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [email_masked, setEmailMasked] = useState('');
  const [categories, setCategories] = useState([]);
  const [prefs, setPrefs] = useState({});

  useEffect(() => {
    if (!token) {
      setError({
        en: 'Missing or invalid preferences link. Please use the link from your email.',
        fr: 'Lien de préférences manquant ou invalide. Veuillez utiliser le lien dans votre courriel.',
      });
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await axios.get(`${API}/email-preferences/verify?token=${encodeURIComponent(token)}`);
        setEmailMasked(res.data.email_masked || '');
        setCategories(res.data.categories || []);
        setPrefs(res.data.preferences || {});
      } catch (err) {
        const detail = err?.response?.data?.detail;
        if (detail === 'token_expired') {
          setError({
            en: 'This preferences link has expired (30-day limit). Request a new one from any BidVex email footer.',
            fr: 'Ce lien de préférences est expiré (limite de 30 jours). Demandez-en un nouveau depuis le bas de page de tout courriel BidVex.',
          });
        } else {
          setError({
            en: 'This preferences link is invalid or has been tampered with.',
            fr: 'Ce lien de préférences est invalide ou a été altéré.',
          });
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const handleToggle = (key) => (checked) => {
    setPrefs((p) => ({ ...p, [key]: checked }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await axios.post(`${API}/email-preferences/update`, {
        token,
        preferences: prefs,
      });
      setPrefs(res.data?.preferences || prefs);
      toast.success('Preferences saved · Préférences enregistrées');
    } catch (err) {
      toast.error('Save failed · Échec de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex justify-center items-center">
        <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4">
        <Card className="border-red-200">
          <CardContent className="pt-6 space-y-3" data-testid="email-prefs-error">
            <div className="flex items-center gap-2 text-red-700">
              <AlertTriangle className="h-5 w-5" />
              <h2 className="font-bold">Link issue · Problème de lien</h2>
            </div>
            <p className="text-sm leading-snug">{error.en}</p>
            <p className="text-sm leading-snug italic text-muted-foreground">{error.fr}</p>
            <Link to="/" className="text-sm text-blue-600 hover:underline inline-flex items-center gap-1">
              <ArrowLeft className="h-3 w-3" />
              Back home · Retour à l'accueil
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-10 px-4" data-testid="email-preferences-page">
      <div className="mb-6 text-center space-y-2">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-700">
          <Mail className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-black">
          Email Preferences · Préférences de courriel
        </h1>
        <p className="text-sm text-muted-foreground">
          Pick which BidVex emails you'd like to receive. · Choisissez les courriels BidVex que vous souhaitez recevoir.
        </p>
        <Badge variant="outline" className="font-mono text-xs">
          {email_masked}
        </Badge>
      </div>

      <Card className="rounded-2xl shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="h-5 w-5 text-emerald-600" />
            Manage categories · Gérer les catégories
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {categories.map((cat) => {
            const isOn = !!prefs[cat.key];
            return (
              <div
                key={cat.key}
                className={`rounded-lg border p-4 flex items-start justify-between gap-3 ${
                  cat.toggleable ? 'border-slate-200 dark:border-slate-700' : 'border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20'
                }`}
                data-testid={`email-pref-row-${cat.key}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-sm">{cat.label_en}</h3>
                    <span className="text-xs text-muted-foreground italic">· {cat.label_fr}</span>
                    {!cat.toggleable && (
                      <Badge className="bg-emerald-600 text-white text-[10px]" data-testid={`email-pref-mandatory-${cat.key}`}>
                        <Lock className="h-2.5 w-2.5 mr-1" />
                        Required · Requis
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground leading-snug mb-1">{cat.description_en}</p>
                  <p className="text-xs text-muted-foreground italic leading-snug">{cat.description_fr}</p>
                </div>
                <div className="shrink-0 pt-1">
                  {cat.toggleable ? (
                    <Switch
                      checked={isOn}
                      onCheckedChange={handleToggle(cat.key)}
                      data-testid={`email-pref-toggle-${cat.key}`}
                    />
                  ) : (
                    <Switch
                      checked
                      disabled
                      data-testid={`email-pref-toggle-${cat.key}-locked`}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Alert className="mt-4 border-blue-200 bg-blue-50">
        <AlertDescription className="text-xs text-blue-900 leading-snug">
          <strong>CASL note · Note LCAP :</strong>{' '}
          BidVex must always send transactional emails (winner notices, receipts, invoices) under
          Canadian Anti-Spam Law §6(6). · BidVex doit toujours envoyer les courriels transactionnels
          (avis de gagnant, reçus, factures) selon la Loi canadienne anti-pourriel §6(6).
        </AlertDescription>
      </Alert>

      <div className="mt-6 flex justify-end gap-2">
        <Button
          asChild
          variant="outline"
          data-testid="email-prefs-back-btn"
        >
          <Link to="/">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back · Retour
          </Link>
        </Button>
        <Button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 text-white"
          data-testid="email-prefs-save-btn"
        >
          {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
          Save · Enregistrer
        </Button>
      </div>
    </div>
  );
};

export default EmailPreferencesPage;
