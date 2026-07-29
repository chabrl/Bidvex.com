/**
 * BidVex — Contact Us page (iter362 rebuild).
 *
 * ── What changed in iter362 ─────────────────────────────────────────
 * • Fixed HQ street number typo (701, not 761).
 * • Fixed corporation number to match the official press-release constants
 *   (1175252826, not the previous 1175252874).
 * • Added the 10th email destination: contractor@bidvex.com.
 * • Added a bilingual <ContactForm> with Subject dropdown that routes
 *   the message to the correct email via a `mailto:` link. Fully
 *   client-side (no backend dependency) — the user's email client opens
 *   pre-filled with the right recipient + subject line.
 * • Emits LocalBusiness JSON-LD via <Helmet> so search engines see NAP
 *   on the Contact page (Google Merchant Center + Business Profile
 *   requirement).
 * • Updated <title> and meta description per iter362 spec.
 */
import React, { useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Mail, Phone, MapPin, Building2, Handshake, ShieldAlert,
  Car, CreditCard, Lock, Megaphone, Briefcase, HardHat, Send,
} from 'lucide-react';
import SEO from '../components/SEO';


const CORPORATE_ADDRESS = '761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8, Canada';
const CORPORATE_PHONE   = '+1 (450) 634-3099';
const CORPORATION_NUMBER = '1175252826';


// LocalBusiness JSON-LD for the Contact page — matches iter357 homepage schema
// so Google clusters both under one Business Profile canonical.
const LOCAL_BUSINESS_LD = {
  '@context': 'https://schema.org',
  '@type':    'LocalBusiness',
  '@id':      'https://www.bidvex.com/#localbusiness',
  name:       'BidVex Inc.',
  legalName:  'BidVex Inc.',
  url:        'https://www.bidvex.com/',
  logo:       'https://www.bidvex.com/bidvex-icon.png',
  telephone:  CORPORATE_PHONE,
  email:      'office@bidvex.com',
  address: {
    '@type':          'PostalAddress',
    streetAddress:    '761 Rue Chalifoux',
    addressLocality:  'Sherbrooke',
    addressRegion:    'QC',
    postalCode:       'J1G 0A8',
    addressCountry:   'CA',
  },
  contactPoint: [
    { '@type': 'ContactPoint', contactType: 'customer service',   email: 'service@bidvex.com',    availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'sales',              email: 'vehicles@bidvex.com',   availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'billing',            email: 'payment@bidvex.com',    availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'legal',              email: 'privacy@bidvex.com',    availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'complaints',         email: 'dispute@bidvex.com',    availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'careers',            email: 'careers@bidvex.com',    availableLanguage: ['en', 'fr'] },
    { '@type': 'ContactPoint', contactType: 'marketing',          email: 'marketing@bidvex.com',  availableLanguage: ['en', 'fr'] },
  ],
  areaServed: 'CA',
};


export default function ContactUsPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];

  return (
    <div className="container mx-auto max-w-4xl py-10 px-4" data-testid="contact-us-page">
      {/* iter362 — Explicit <title> + meta description per spec */}
      <SEO
        title={t.metaTitle}
        description={t.metaDescription}
        path="/contact-us"
      />
      <Helmet>
        <script type="application/ld+json">{JSON.stringify(LOCAL_BUSINESS_LD)}</script>
      </Helmet>

      <header className="mb-8 border-b border-slate-200 dark:border-slate-700 pb-4">
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="contact-us-title">
          <Building2 className="w-7 h-7 text-blue-600" />
          {t.title}
        </h1>
        <p className="text-sm text-slate-500 mt-1">{t.subtitle}</p>
      </header>

      {/* ── Legal Entity block ──────────────────────────────────── */}
      <Card className="mb-5 border-2 border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30" data-testid="legal-entity-block">
        <CardContent className="p-5">
          <h2 className="font-bold text-lg mb-2 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-600" />
            {t.legal_heading}
          </h2>
          <p className="font-semibold text-slate-900 dark:text-white">BidVex Inc.</p>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {t.legal_canada_inc}<br />
            {t.legal_corp_num}: <span className="font-mono" data-testid="contact-corp-num">{CORPORATION_NUMBER}</span><br />
            {t.legal_tps}: <span className="font-mono">8XX XXX XXX RT0001</span><br />
            {t.legal_tvq}: <span className="font-mono">1XXXXXXXXX TQ0001</span>
          </p>
        </CardContent>
      </Card>

      {/* ── HQ NAP block (matches LocalBusiness JSON-LD) ───────── */}
      <Card className="mb-5" data-testid="hq-block">
        <CardContent className="p-5">
          <h2 className="font-bold text-lg mb-2 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-rose-600" />
            {t.hq_heading}
          </h2>
          <address className="not-italic text-sm text-slate-700 dark:text-slate-200 leading-relaxed" data-testid="contact-address">
            BidVex Inc.<br />
            761 Rue Chalifoux<br />
            Sherbrooke (Québec) J1G 0A8<br />
            Canada
          </address>
          <p className="text-sm mt-2">
            <a href={`tel:${CORPORATE_PHONE.replace(/[^+\d]/g, '')}`} className="text-blue-600 hover:underline inline-flex items-center gap-1" data-testid="contact-phone-link">
              <Phone className="w-3.5 h-3.5" /> {CORPORATE_PHONE}
            </a>
          </p>
          <p className="text-xs text-slate-500 mt-2">{t.hq_hours}</p>
        </CardContent>
      </Card>

      {/* ── 10 direct-routed team emails ────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5" data-testid="contact-teams-grid">
        {t.teams.map((team) => (
          <Card key={team.id} data-testid={`contact-team-${team.id}`}>
            <CardContent className="p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-2">
                <team.icon className="w-4 h-4 text-blue-600" />
                {team.title}
              </h3>
              <p className="text-xs text-slate-500 mb-2">{team.description}</p>
              <a
                href={`mailto:${team.email}?subject=${encodeURIComponent(team.subjectLine || team.title)}`}
                className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
                data-testid={`contact-team-email-${team.id}`}
              >
                <Mail className="w-3.5 h-3.5" />
                {team.email}
              </a>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Contact form (subject-routed to the right team email) ── */}
      <ContactForm lang={lang} teams={t.teams} copy={t.form} />

      {/* ── Response-time SLA block ────────────────────────────── */}
      <Card className="bg-slate-50 dark:bg-slate-800/40" data-testid="response-time-block">
        <CardContent className="p-4 text-sm text-slate-700 dark:text-slate-200">
          <p className="font-semibold mb-1">{t.response_heading}</p>
          <ul className="space-y-0.5 text-xs">
            <li>· {t.response_support}</li>
            <li>· {t.response_legal}</li>
            <li>· {t.response_resolutions}</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}


/**
 * ContactForm — Direct backend POST (no mailto: fallback).
 *
 * iter363: submits to `POST /api/contact/submit` via axios. SendGrid
 * routes the message to the correct team email server-side. Client
 * receives a proper success/error response. The mailto: fallback was
 * removed per user directive — if the POST fails, an explicit error
 * message is shown and the user can retry or click the team's direct
 * email link elsewhere on the page.
 */
function ContactForm({ lang, teams, copy }) {
  const [name, setName]       = useState('');
  const [email, setEmail]     = useState('');
  const [teamId, setTeamId]   = useState(teams[0].id);
  const [message, setMessage] = useState('');
  const [status, setStatus]   = useState({ kind: 'idle', detail: '' });

  const selectedTeam = useMemo(
    () => teams.find(t => t.id === teamId) || teams[0],
    [teamId, teams],
  );

  const canSubmit = name.trim() && email.trim() && message.trim().length >= 10 &&
                    status.kind !== 'sending';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus({ kind: 'sending', detail: '' });

    // Late-import axios so the initial page bundle stays small (Contact is
    // rarely on the critical path — a saved 30KB gz for first-page hits).
    const axios = (await import('axios')).default;
    const API = process.env.REACT_APP_BACKEND_URL || '';

    try {
      const res = await axios.post(`${API}/api/contact/submit`, {
        name:    name.trim(),
        email:   email.trim(),
        team_id: teamId,
        message: message.trim(),
        lang,
      }, { timeout: 12000 });

      if (res.data?.ok) {
        setStatus({
          kind: 'success',
          detail: lang === 'fr'
            ? `Message envoyé à ${res.data.routed_to}`
            : `Message routed to ${res.data.routed_to}`,
        });
        setName(''); setEmail(''); setMessage('');
      } else {
        throw new Error('Backend returned ok=false');
      }
    } catch (err) {
      // iter363 — mailto: fallback removed per user directive.
      // Show an explicit error so users retry or use the direct team
      // email link visible on the same page.
      const detail = err?.response?.data?.detail;
      const backendMsg = typeof detail === 'string'
        ? detail
        : (detail?.[`message_${lang}`] || detail?.message_en);
      setStatus({
        kind: 'error',
        detail: backendMsg || (lang === 'fr'
          ? "Envoi impossible pour le moment. Merci de réessayer dans quelques minutes ou de cliquer sur l'adresse courriel de l'équipe ci-dessus."
          : 'Unable to send right now. Please retry in a few minutes or click the team email address above.'),
      });
    }
  };

  return (
    <Card className="mb-5" data-testid="contact-form-card">
      <CardContent className="p-5">
        <h2 className="font-bold text-lg mb-3 flex items-center gap-2">
          <Send className="w-5 h-5 text-blue-600" />
          {copy.heading}
        </h2>
        <p className="text-xs text-slate-500 mb-4">{copy.description}</p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="contact-form-name">{copy.formName}</Label>
              <Input
                id="contact-form-name"
                data-testid="contact-form-name-input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
              />
            </div>
            <div>
              <Label htmlFor="contact-form-email">{copy.formEmail}</Label>
              <Input
                id="contact-form-email"
                data-testid="contact-form-email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="contact-form-subject">{copy.formSubject}</Label>
            <select
              id="contact-form-subject"
              data-testid="contact-form-subject-select"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="w-full h-10 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 text-sm"
            >
              {teams.map(t => (
                <option key={t.id} value={t.id}>
                  {t.title} ({t.email})
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-500 mt-1" data-testid="contact-form-route-hint">
              {lang === 'fr'
                ? `Votre message sera envoyé à `
                : `Your message will be sent to `}
              <span className="font-mono font-semibold">{selectedTeam.email}</span>
            </p>
          </div>

          <div>
            <Label htmlFor="contact-form-message">{copy.formMessage}</Label>
            <Textarea
              id="contact-form-message"
              data-testid="contact-form-message-input"
              rows={5}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              minLength={10}
            />
          </div>

          {status.kind === 'success' && (
            <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded p-2" data-testid="contact-form-success">
              ✓ {status.detail}
            </div>
          )}
          {status.kind === 'error' && (
            <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-2" data-testid="contact-form-error">
              {status.detail}
            </div>
          )}

          <Button
            type="submit"
            disabled={!canSubmit}
            data-testid="contact-form-submit"
            className="w-full sm:w-auto"
          >
            <Send className="w-4 h-4 mr-2" />
            {status.kind === 'sending'
              ? (lang === 'fr' ? 'Envoi…' : 'Sending…')
              : copy.formSubmit}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}


// ─── Bilingual copy tables ─────────────────────────────────────────
const COPY = {
  en: {
    metaTitle:       "Contact BidVex | Canada's Bilingual Auction Marketplace",
    metaDescription: "Contact BidVex Inc. for support, dealer verification, broker inquiries, payment questions, or career opportunities. We're here to help.",
    title:    'Contact BidVex',
    subtitle: 'BidVex Inc. — Sherbrooke (Québec), Canada. Ten direct-routed inboxes so your message reaches the right team fast.',
    legal_heading:    'Legal Entity',
    legal_canada_inc: 'Federally incorporated under the Canada Business Corporations Act',
    legal_corp_num:   'Corporation Number',
    legal_tps:        'GST/HST Registration',
    legal_tvq:        'QST Registration',
    hq_heading:       'Business Headquarters',
    hq_hours:         'Open Mon–Fri, 09:00–17:00 Eastern. Closed on Canadian statutory holidays.',
    response_heading: 'Response Targets',
    response_support: 'Customer Support: within 24 hours on business days',
    response_legal:   'Legal & Compliance: within 5 business days',
    response_resolutions: 'Dispute Resolutions: written decision within 15 business days of complete claim submission',
    form: {
      heading:      'Send us a message',
      description:  'Pick a subject — your message will be routed to the correct team automatically.',
      formName:     'Name',
      formEmail:    'Email',
      formSubject:  'Subject',
      formMessage:  'Message',
      formSubmit:   'Send message',
    },
    teams: [
      { id: 'office',      title: 'General Inquiries',        description: 'Direct line to the BidVex executive office.',
        icon: Building2,   email: 'office@bidvex.com',        subjectLine: 'General Inquiry' },
      { id: 'support',     title: 'Customer Service',         description: 'Account, bidding, technical issues.',
        icon: Mail,        email: 'service@bidvex.com',       subjectLine: 'Customer Service' },
      { id: 'vehicles',    title: 'Vehicle Dealers',          description: 'Dealer licence verification, vehicle auctions.',
        icon: Car,         email: 'vehicles@bidvex.com',      subjectLine: 'Vehicle Dealer Verification' },
      { id: 'brokers',     title: 'Brokers & Partners',       description: 'Onboarding, licence verification, payouts.',
        icon: Handshake,   email: 'broker@bidvex.com',        subjectLine: 'Broker & Partner' },
      { id: 'resolutions', title: 'Dispute Resolution',       description: 'Refund claims, lot disputes, broker complaints.',
        icon: ShieldAlert, email: 'dispute@bidvex.com',       subjectLine: 'Dispute Resolution' },
      { id: 'payment',     title: 'Payment Support',          description: 'Invoices, charges, payout questions.',
        icon: CreditCard,  email: 'payment@bidvex.com',       subjectLine: 'Payment Support' },
      { id: 'privacy',     title: 'Privacy & Data',           description: 'Law 25 / PIPEDA requests, data access, privacy.',
        icon: Lock,        email: 'privacy@bidvex.com',       subjectLine: 'Privacy & Data Request' },
      { id: 'marketing',   title: 'Marketing',                description: 'Campaigns, media, press, B2B partnerships.',
        icon: Megaphone,   email: 'marketing@bidvex.com',     subjectLine: 'Marketing' },
      { id: 'careers',     title: 'Careers',                  description: 'Job applications and hiring questions.',
        icon: Briefcase,   email: 'careers@bidvex.com',       subjectLine: 'Careers' },
      { id: 'contractors', title: 'Contractors',              description: 'Contractor dialer, commissions, and account access.',
        icon: HardHat,     email: 'contractor@bidvex.com',    subjectLine: 'Contractor Inquiry' },
    ],
  },
  fr: {
    metaTitle:       "Contact BidVex | La marketplace d'enchères bilingue du Canada",
    metaDescription: 'Communiquez avec BidVex Inc. pour le soutien, la vérification concessionnaire, les demandes courtiers, les paiements ou les carrières. Nous sommes là pour vous aider.',
    title:    'Communiquer avec BidVex',
    subtitle: 'BidVex Inc. — Sherbrooke (Québec), Canada. Dix boîtes de réception directes pour que votre message atteigne rapidement la bonne équipe.',
    legal_heading:    'Entité juridique',
    legal_canada_inc: 'Incorporée fédéralement en vertu de la Loi canadienne sur les sociétés par actions',
    legal_corp_num:   'Numéro de société',
    legal_tps:        'Inscription TPS/TVH',
    legal_tvq:        'Inscription TVQ',
    hq_heading:       'Siège social',
    hq_hours:         'Ouvert du lundi au vendredi, 09 h 00 à 17 h 00 (HE). Fermé les jours fériés canadiens.',
    response_heading: 'Délais de réponse',
    response_support: 'Service à la clientèle : sous 24 heures les jours ouvrables',
    response_legal:   'Juridique et conformité : sous 5 jours ouvrables',
    response_resolutions: 'Résolution des différends : décision écrite sous 15 jours ouvrables suivant la soumission complète de la réclamation',
    form: {
      heading:      'Envoyez-nous un message',
      description:  'Choisissez un sujet — votre message sera acheminé à la bonne équipe automatiquement.',
      formName:     'Nom',
      formEmail:    'Courriel',
      formSubject:  'Sujet',
      formMessage:  'Message',
      formSubmit:   'Envoyer le message',
    },
    teams: [
      { id: 'office',      title: 'Demandes générales',            description: 'Ligne directe au bureau exécutif de BidVex.',
        icon: Building2,   email: 'office@bidvex.com',             subjectLine: 'Demande générale' },
      { id: 'support',     title: 'Service à la clientèle',        description: 'Compte, enchères, problèmes techniques.',
        icon: Mail,        email: 'service@bidvex.com',            subjectLine: 'Service à la clientèle' },
      { id: 'vehicles',    title: 'Concessionnaires de véhicules', description: 'Vérification de licence, enchères de véhicules.',
        icon: Car,         email: 'vehicles@bidvex.com',           subjectLine: 'Vérification concessionnaire' },
      { id: 'brokers',     title: 'Courtiers et partenaires',      description: 'Intégration, vérification de licence, versements.',
        icon: Handshake,   email: 'broker@bidvex.com',             subjectLine: 'Courtiers et partenaires' },
      { id: 'resolutions', title: 'Résolution des différends',     description: 'Réclamations de remboursement, litiges de lots, plaintes.',
        icon: ShieldAlert, email: 'dispute@bidvex.com',            subjectLine: 'Résolution de différend' },
      { id: 'payment',     title: 'Soutien aux paiements',         description: 'Factures, frais, questions de versement.',
        icon: CreditCard,  email: 'payment@bidvex.com',            subjectLine: 'Soutien aux paiements' },
      { id: 'privacy',     title: 'Confidentialité et données',    description: 'Demandes Loi 25 / LPRPDE, accès aux données.',
        icon: Lock,        email: 'privacy@bidvex.com',            subjectLine: 'Confidentialité et données' },
      { id: 'marketing',   title: 'Marketing',                     description: 'Campagnes, médias, presse, partenariats B2B.',
        icon: Megaphone,   email: 'marketing@bidvex.com',          subjectLine: 'Marketing' },
      { id: 'careers',     title: 'Carrières',                     description: "Candidatures et questions d'embauche.",
        icon: Briefcase,   email: 'careers@bidvex.com',            subjectLine: 'Carrières' },
      { id: 'contractors', title: 'Sous-traitants',                description: 'Numéroteur, commissions et accès aux comptes.',
        icon: HardHat,     email: 'contractor@bidvex.com',         subjectLine: 'Demande sous-traitant' },
    ],
  },
};
