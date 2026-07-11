/**
 * BidVex — Contact Us page.
 *
 * Required by Google Merchant Center for marketplace transparency. Lists
 * the legal entity name, HQ address, public-facing email + phone, and
 * direct-routed teams (Support, Legal, Resolutions, Brokers, Press).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { Mail, Phone, MapPin, Building2, Scale, Handshake, Newspaper, ShieldAlert, Car, CreditCard, Lock, Megaphone, Briefcase } from 'lucide-react';
// iter268 Mission 4 — SEO meta tags
import SEO from '../components/SEO';

export default function ContactUsPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];

  return (
    <div className="container mx-auto max-w-3xl py-10 px-4" data-testid="contact-us-page">
      <SEO
        title="Contact BidVex — Support & Legal"
        description="Get in touch with BidVex. Support, legal, broker, and press contacts for Canada's online auction marketplace."
        path="/contact-us"
      />
      <header className="mb-8 border-b border-slate-200 dark:border-slate-700 pb-4">
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="contact-us-title">
          <Building2 className="w-7 h-7 text-blue-600" />
          {t.title}
        </h1>
        <p className="text-sm text-slate-500 mt-1">{t.subtitle}</p>
      </header>

      <Card className="mb-5 border-2 border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30" data-testid="legal-entity-block">
        <CardContent className="p-5">
          <h2 className="font-bold text-lg mb-2 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-600" />
            {t.legal_heading}
          </h2>
          <p className="font-semibold text-slate-900 dark:text-white">BidVex Inc.</p>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {t.legal_canada_inc}<br />
            {t.legal_corp_num}: <span className="font-mono">1175252874</span><br />
            {t.legal_tps}: <span className="font-mono">8XX XXX XXX RT0001</span><br />
            {t.legal_tvq}: <span className="font-mono">1XXXXXXXXX TQ0001</span>
          </p>
        </CardContent>
      </Card>

      <Card className="mb-5" data-testid="hq-block">
        <CardContent className="p-5">
          <h2 className="font-bold text-lg mb-2 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-rose-600" />
            {t.hq_heading}
          </h2>
          <address className="not-italic text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
            BidVex Inc.<br />
            761 Rue Chalifoux<br />
            Sherbrooke (Québec) J1G 0A8<br />
            Canada
          </address>
          <p className="text-xs text-slate-500 mt-2">{t.hq_hours}</p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        {t.teams.map((team, i) => (
          <Card key={i} data-testid={`contact-team-${team.id}`}>
            <CardContent className="p-4">
              <h3 className="font-semibold flex items-center gap-2 mb-2">
                <team.icon className="w-4 h-4 text-blue-600" />
                {team.title}
              </h3>
              <p className="text-xs text-slate-500 mb-2">{team.description}</p>
              <div className="space-y-1 text-sm">
                <a
                  href={`mailto:${team.email}${team.subjectLine ? `?subject=${encodeURIComponent(team.subjectLine)}` : ''}`}
                  className="flex items-center gap-2 text-blue-600 hover:underline"
                  data-testid={`contact-team-email-${team.id}`}
                >
                  <Mail className="w-3.5 h-3.5" />
                  {team.email}
                  {team.subjectLine && (
                    <span className="text-[10px] text-slate-400 font-normal ml-1">
                      ({lang === 'fr' ? 'Objet' : 'Subject'}: {team.subjectLine})
                    </span>
                  )}
                </a>
                {team.phone && (
                  <a href={`tel:${team.phone.replace(/[^+\d]/g, '')}`} className="flex items-center gap-2 text-blue-600 hover:underline" data-testid={`contact-team-phone-${team.id}`}>
                    <Phone className="w-3.5 h-3.5" />
                    {team.phone}
                  </a>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

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

const COPY = {
  en: {
    title:    'Contact BidVex',
    subtitle: 'BidVex Inc. — Sherbrooke, QC, Canada. Below are our verified contact channels.',
    legal_heading:   'Legal Entity',
    legal_canada_inc: 'Federally incorporated under the Canada Business Corporations Act',
    legal_corp_num:  'Corporation Number',
    legal_tps:       'GST/HST Registration',
    legal_tvq:       'QST Registration',
    hq_heading:      'Business Headquarters',
    hq_hours:        'Open Mon–Fri, 09:00–17:00 Eastern. Closed on Canadian statutory holidays.',
    response_heading: 'Response Targets',
    response_support: 'Customer Support: within 24 hours on business days',
    response_legal:   'Legal & Compliance: within 5 business days',
    response_resolutions: 'Dispute Resolutions: written decision within 15 business days of complete claim submission',
    teams: [
      { id: 'office',      title: 'General Inquiries',        description: 'Direct line to the BidVex executive office.',
        icon: Building2,   email: 'office@bidvex.com',        phone: '+1 (450) 634-3099' },
      { id: 'support',     title: 'Customer Service',         description: 'Account, bidding, technical issues.',
        icon: Mail,        email: 'service@bidvex.com',       phone: '+1 (450) 634-3099' },
      { id: 'vehicles',    title: 'Vehicle Dealers',          description: 'Dealer licence verification, vehicle auctions.',
        icon: Car,         email: 'vehicles@bidvex.com',      phone: null,
        subjectLine: 'Vehicle Dealer Verification' },
      { id: 'brokers',     title: 'Brokers & Partners',       description: 'Onboarding, licence verification, payouts.',
        icon: Handshake,   email: 'broker@bidvex.com',        phone: null,
        subjectLine: 'Broker & Partner' },
      { id: 'resolutions', title: 'Dispute Resolution',       description: 'Refund claims, lot disputes, broker complaints.',
        icon: ShieldAlert, email: 'dispute@bidvex.com',       phone: null,
        subjectLine: 'Dispute Resolution' },
      { id: 'payment',     title: 'Payment Support',          description: 'Invoices, charges, payout questions.',
        icon: CreditCard,  email: 'payment@bidvex.com',       phone: null,
        subjectLine: 'Payment Support' },
      { id: 'privacy',     title: 'Privacy & Data',           description: 'Law 25 / PIPEDA requests, data access, privacy.',
        icon: Lock,        email: 'privacy@bidvex.com',       phone: null,
        subjectLine: 'Privacy & Data' },
      { id: 'marketing',   title: 'Marketing',                description: 'Campaigns, media, press, B2B partnerships.',
        icon: Megaphone,   email: 'marketing@bidvex.com',     phone: null,
        subjectLine: 'Marketing' },
      { id: 'careers',     title: 'Careers',                  description: 'Job applications and hiring questions.',
        icon: Briefcase,   email: 'careers@bidvex.com',       phone: null,
        subjectLine: 'Careers' },
    ],
  },
  fr: {
    title:    'Communiquer avec BidVex',
    subtitle: 'BidVex Inc. — Sherbrooke (Québec), Canada. Voici nos canaux de contact vérifiés.',
    legal_heading:   'Entité juridique',
    legal_canada_inc: 'Incorporée fédéralement en vertu de la Loi canadienne sur les sociétés par actions',
    legal_corp_num:  'Numéro de société',
    legal_tps:       'Inscription TPS/TVH',
    legal_tvq:       'Inscription TVQ',
    hq_heading:      'Siège social',
    hq_hours:        'Ouvert du lundi au vendredi, 09 h 00 à 17 h 00 (HE). Fermé les jours fériés canadiens.',
    response_heading: 'Délais de réponse',
    response_support: 'Service à la clientèle : sous 24 heures les jours ouvrables',
    response_legal:   'Juridique et conformité : sous 5 jours ouvrables',
    response_resolutions: 'Résolution des différends : décision écrite sous 15 jours ouvrables suivant la soumission complète de la réclamation',
    teams: [
      { id: 'office',      title: 'Demandes générales',       description: 'Ligne directe au bureau exécutif de BidVex.',
        icon: Building2,   email: 'office@bidvex.com',        phone: '+1 (450) 634-3099' },
      { id: 'support',     title: 'Service à la clientèle',   description: 'Compte, enchères, problèmes techniques.',
        icon: Mail,        email: 'service@bidvex.com',       phone: '+1 (450) 634-3099' },
      { id: 'vehicles',    title: 'Concessionnaires de véhicules', description: 'Vérification de licence, enchères de véhicules.',
        icon: Car,         email: 'vehicles@bidvex.com',      phone: null,
        subjectLine: 'Vérification concessionnaire' },
      { id: 'brokers',     title: 'Courtiers et partenaires', description: 'Intégration, vérification de licence, versements.',
        icon: Handshake,   email: 'broker@bidvex.com',        phone: null,
        subjectLine: 'Courtiers et partenaires' },
      { id: 'resolutions', title: 'Résolution des différends', description: 'Réclamations de remboursement, litiges de lots, plaintes.',
        icon: ShieldAlert, email: 'dispute@bidvex.com',       phone: null,
        subjectLine: 'Résolution de différend' },
      { id: 'payment',     title: 'Soutien aux paiements',    description: 'Factures, frais, questions de versement.',
        icon: CreditCard,  email: 'payment@bidvex.com',       phone: null,
        subjectLine: 'Soutien aux paiements' },
      { id: 'privacy',     title: 'Confidentialité et données', description: 'Demandes Loi 25 / LPRPDE, accès aux données.',
        icon: Lock,        email: 'privacy@bidvex.com',       phone: null,
        subjectLine: 'Confidentialité et données' },
      { id: 'marketing',   title: 'Marketing',                description: 'Campagnes, médias, presse, partenariats B2B.',
        icon: Megaphone,   email: 'marketing@bidvex.com',     phone: null,
        subjectLine: 'Marketing' },
      { id: 'careers',     title: 'Carrières',                description: 'Candidatures et questions d\'embauche.',
        icon: Briefcase,   email: 'careers@bidvex.com',       phone: null,
        subjectLine: 'Carrières' },
    ],
  },
};
