/**
 * iter217 Phase 5 Hotfix v8.1 — Public Buyer Transaction Receipt.
 *
 * Route: /my-receipt/:invoice_id?code=<12-char token>
 *
 * Token-secured public page. Returns 404 (not 403) when the token
 * does not match. No login required. Bilingual EN/FR toggle that
 * inherits the user's base site language. PDF export hits the same
 * backend route with `/pdf` suffix.
 *
 * Sanitization: buyer name is masked server-side to "First L." — no
 * email, phone, or full identity is exposed.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import SEO from '../components/SEO';
import {
  ShieldCheck, FileDown, Printer, AlertTriangle, CheckCircle2,
  Car, User, Briefcase, FileText, Loader2,
} from 'lucide-react';

const _fmt = (n) =>
  (n == null || Number.isNaN(Number(n)))
    ? '—'
    : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n));

const _date = (v) => {
  if (!v) return '—';
  try { return new Date(v).toLocaleDateString('en-CA'); } catch { return '—'; }
};

export default function MyReceiptPage() {
  const { i18n } = useTranslation();
  const { invoice_id } = useParams();
  const [params] = useSearchParams();
  const code = params.get('code');

  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNF]     = useState(false);
  const [lang, setLang]       = useState(i18n.language?.startsWith('fr') ? 'fr' : 'en');
  const isFR = lang === 'fr';

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!code) { setNF(true); setLoading(false); return; }
      try {
        const r = await axios.get(`${API_BASE}/broker-invoices/${invoice_id}/receipt?code=${encodeURIComponent(code)}`);
        if (mounted) setData(r.data);
      } catch (e) {
        if (mounted) setNF(true);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [invoice_id, code]);

  const downloadPdf = () => {
    const url = `${API_BASE}/broker-invoices/${invoice_id}/receipt/pdf?code=${encodeURIComponent(code)}&lang=${lang}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  if (loading) {
    return <div className="container mx-auto max-w-2xl py-16 text-center text-slate-500" data-testid="receipt-loading">
      <Loader2 className="inline h-6 w-6 animate-spin mr-2" />
      {isFR ? 'Chargement…' : 'Loading…'}
    </div>;
  }

  if (notFound || !data) {
    return (
      <div className="container mx-auto max-w-md py-16 text-center" data-testid="receipt-not-found">
        <AlertTriangle className="mx-auto h-12 w-12 text-amber-500 mb-4" />
        <h1 className="text-xl font-semibold mb-2">{isFR ? 'Reçu introuvable' : 'Receipt not found'}</h1>
        <p className="text-sm text-slate-500">
          {isFR
            ? 'Le lien que vous avez utilisé est invalide ou expiré. Veuillez vérifier auprès de votre courtier.'
            : 'The link you used is invalid or expired. Please verify with your broker.'}
        </p>
      </div>
    );
  }

  const v   = data.vehicle  || {};
  const tx  = data.transaction || {};
  const fees = data.fees_via_stripe || {};
  const ttFiled = !!tx.title_transfer_logged_at;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-8 print:py-0 print:bg-white">
      <SEO
        title={isFR ? `Reçu ${data.invoice_number} — BidVex` : `Receipt ${data.invoice_number} — BidVex`}
        noindex
      />

      <div className="container mx-auto max-w-3xl px-4">
        {/* Top action bar — hidden on print */}
        <div className="flex items-center justify-between mb-4 print:hidden">
          <div className="flex gap-1 bg-white dark:bg-slate-800 rounded-full p-1 border border-slate-200 dark:border-slate-700" data-testid="receipt-lang-toggle">
            <button onClick={() => setLang('en')} data-testid="receipt-lang-en"
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${!isFR ? 'bg-[#1E3A8A] text-white' : 'text-slate-500'}`}>EN</button>
            <button onClick={() => setLang('fr')} data-testid="receipt-lang-fr"
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${isFR ? 'bg-[#1E3A8A] text-white' : 'text-slate-500'}`}>FR</button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => window.print()} data-testid="receipt-print-btn">
              <Printer className="h-4 w-4 mr-1.5" />{isFR ? 'Imprimer' : 'Print'}
            </Button>
            <Button size="sm" onClick={downloadPdf} className="bg-[#1E3A8A] text-white" data-testid="receipt-pdf-btn">
              <FileDown className="h-4 w-4 mr-1.5" />{isFR ? 'Télécharger PDF' : 'Download PDF'}
            </Button>
          </div>
        </div>

        <Card className="shadow-xl" data-testid="receipt-card">
          {/* Header */}
          <CardContent className="p-0">
            <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white px-6 py-6">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-cyan-100 mb-1 flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5" /> {isFR ? 'BidVex — Marché vérifié' : 'BidVex Marketplace Verified'}
                  </p>
                  <h1 className="text-2xl font-bold">🔒 {isFR ? 'Reçu officiel de transaction' : 'Official Transaction Receipt'}</h1>
                  <p className="text-sm text-cyan-100 mt-1">
                    {isFR ? 'Facture' : 'Invoice'} <strong data-testid="receipt-invoice-number">{data.invoice_number}</strong>
                    {' · '}{_date(data.issued_at)}
                  </p>
                </div>
                <div className="text-right text-xs text-cyan-100">
                  <p className="font-semibold text-white">{data.broker?.legal_business_name}</p>
                  <p>{isFR ? 'Permis' : 'License'} {data.broker?.license_masked}</p>
                  <p>{data.broker?.operating_province} · {data.broker?.regulatory_body}</p>
                </div>
              </div>
            </div>

            {/* Vehicle */}
            <Section icon={<Car className="h-4 w-4" />} title={isFR ? 'Véhicule' : 'Vehicle Details'} testId="receipt-section-vehicle">
              <KV label={isFR ? 'Titre' : 'Title'}              value={v.title || '—'} />
              <KV label={isFR ? 'Année / Marque / Modèle' : 'Year / Make / Model'}
                  value={[v.year, v.make, v.model].filter(Boolean).join(' ') || '—'} />
              <KV label="VIN"                                    value={v.vin || '—'} />
              <KV label={isFR ? 'Kilométrage' : 'Mileage'}      value={v.mileage || '—'} />
              <KV label={isFR ? 'Origine' : 'Origin'}           value={`${v.origin_province || '—'}${v.country ? ', ' + v.country : ''}`} />
            </Section>

            {/* Parties */}
            <Section icon={<User className="h-4 w-4" />} title={isFR ? 'Parties' : 'Parties'} testId="receipt-section-parties">
              <KV label={isFR ? 'Acheteur' : 'Buyer'}            value={<span data-testid="receipt-buyer-display">{data.buyer?.display_name}</span>} />
              <KV label={isFR ? 'Courtier licencié' : 'Licensed Broker'} value={data.broker?.legal_business_name} />
              <KV label={isFR ? 'N° de permis' : 'License #'}   value={data.broker?.license_masked} />
              <KV label={isFR ? 'Registre' : 'Registry'}        value={`${data.broker?.regulatory_body || '—'} (${data.broker?.operating_province || ''})`} />
            </Section>

            {/* Transaction */}
            <Section icon={<Briefcase className="h-4 w-4" />} title={isFR ? 'Détails de la transaction' : 'Transaction Details'} testId="receipt-section-transaction">
              {/* Hammer — amber callout */}
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-md p-3 mb-3">
                <div className="flex justify-between items-baseline">
                  <span className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                    {isFR ? 'Prix marteau (réglé directement avec le courtier)' : 'Hammer Price (settled directly with broker offline)'}
                  </span>
                  <span className="text-lg font-bold text-amber-900 dark:text-amber-200" data-testid="receipt-hammer">
                    {_fmt(tx.hammer_price_cad)}
                  </span>
                </div>
                <p className="text-[11px] text-amber-700 dark:text-amber-300 mt-1">{tx.hammer_settlement_note}</p>
              </div>
              <KV label={isFR ? 'Enchère fermée' : 'Auction Date'}        value={_date(tx.auction_closed_at)} />
              <KV label={isFR ? 'Véhicule remis' : 'Vehicle Released'}    value={_date(tx.vehicle_released_at)} />
              <KV label={isFR ? 'Transfert de propriété' : 'Title Transfer Filed'}
                  value={ttFiled
                    ? <span className="inline-flex items-center gap-1.5 text-emerald-600 font-medium" data-testid="receipt-title-filed">
                        <CheckCircle2 className="h-4 w-4" />
                        {tx.title_transfer_registry} {tx.title_transfer_tx_number}
                      </span>
                    : <span className="text-amber-600 font-medium" data-testid="receipt-title-pending">
                        {isFR ? 'En attente' : 'Pending'}
                      </span>} />
              {ttFiled && <KV label={isFR ? 'Date du transfert' : 'Title Transfer Date'} value={_date(tx.title_transfer_date)} />}
            </Section>

            {/* Fees via Stripe */}
            <Section icon={<FileText className="h-4 w-4" />} title={isFR ? 'Frais traités via BidVex (Stripe)' : 'Fees Processed via BidVex (Stripe)'} testId="receipt-section-fees">
              <KV label={isFR ? 'Frais de plateforme BidVex' : 'BidVex Platform Fee'} value={_fmt(fees.platform_fee_cad)} />
              <KV label={isFR ? 'Frais de service du courtier' : 'Broker Service Fee'} value={_fmt(fees.broker_fee_cad)} />
              <KV label={isFR ? 'TPS (5 %)' : 'GST (5%)'}                value={_fmt(fees.gst_cad)} />
              {Number(fees.qst_cad || 0) > 0 && (
                <KV label={isFR ? 'TVQ (9,975 %) [QC]' : 'QST (9.975%) [QC]'} value={_fmt(fees.qst_cad)} />
              )}
              <KV label={isFR ? 'Frais de traitement Stripe' : 'Stripe Processing Fee'} value={_fmt(fees.stripe_processing_fee_cad)} />
              <div className="border-t-2 border-[#1E3A8A] mt-3 pt-2 flex justify-between items-baseline">
                <span className="text-sm font-bold">{isFR ? 'Total via Stripe' : 'Total via Stripe'}</span>
                <span className="text-xl font-bold text-[#1E3A8A] dark:text-cyan-300" data-testid="receipt-total-stripe">
                  {_fmt(fees.total_via_stripe_cad)}
                </span>
              </div>
            </Section>

            {/* Disclaimer */}
            <div className="px-6 py-4 bg-amber-50 dark:bg-amber-950/30 border-t border-amber-200 dark:border-amber-900">
              <div className="flex gap-2 items-start">
                <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800 dark:text-amber-200 leading-relaxed">
                  {data.platform_disclaimer}
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-slate-100 dark:bg-slate-800 text-center text-[11px] text-slate-500">
              <p className="font-semibold text-slate-700 dark:text-slate-200">
                {isFR ? 'Vérifié par BidVex Inc.' : 'Verified by BidVex Inc.'} — {data.platform_address}
              </p>
              <p className="mt-1">{data.gst_registration} · {data.qst_registration}</p>
            </div>
          </CardContent>
        </Card>

        <p className="text-center text-[11px] text-slate-400 mt-4 print:hidden">
          {isFR
            ? 'Ce reçu est partageable. Le code dans l\'URL agit comme une clé de vérification.'
            : 'This receipt is shareable. The code in the URL acts as a verification key.'}
        </p>
      </div>
    </div>
  );
}

function Section({ icon, title, children, testId }) {
  return (
    <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800" data-testid={testId}>
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-3">
        {icon} {title}
      </p>
      <div>{children}</div>
    </div>
  );
}

function KV({ label, value }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 gap-3 border-b border-slate-50 dark:border-slate-800 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-sm text-slate-900 dark:text-white text-right">{value}</span>
    </div>
  );
}
