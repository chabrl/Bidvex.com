/**
 * iter225 Task 3 — Broker Liability Agreement Modal.
 *
 * Bilingual three-tier legal disclaimer with FORCED 100% scroll-to-bottom
 * gate before the digital signature input + "Accept & Sign" button unlock.
 *
 * Sections:
 *   1. Liability Acceptance — broker assumes 100% legal responsibility for
 *      all interactions between their managed buyers and sellers/dealers.
 *   2. Platform Immunity — BidVex is a marketplace platform, not a party
 *      to vehicle transactions. Broker cannot make claims against BidVex.
 *   3. Data / Audit Consent — broker bid stream, KYC docs, and contracts
 *      are immutably logged and may be disclosed to provincial regulators.
 *
 * Submits to POST /api/brokers/sign-liability.
 */
import React, { useRef, useState, useEffect } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Alert, AlertDescription } from '../ui/alert';
import { CheckCircle2, AlertTriangle, ScrollText, ChevronDown, X, ShieldAlert, Scale, Lock } from 'lucide-react';

const COPY = {
  en: {
    title:        'Broker Liability Agreement',
    subtitle:     'You must scroll through all three sections and accept each one before signing.',
    scroll_hint:  'Scroll to the very bottom to enable the signature field.',
    s1_title:     'Section 1 — 100% Liability Acceptance',
    s1_text: (
      <>
        <p>I, the undersigned licensed Broker, hereby accept FULL AND EXCLUSIVE LEGAL LIABILITY for every interaction, communication, transaction, bid, contract, settlement, vehicle release, title transfer, and after-sale dispute that occurs between any buyer I manage on the BidVex platform and any seller, dealer, auctioneer, partner, facility, or third party.</p>
        <p>I confirm I hold all required provincial registrations and bonds and that my licence remains in good standing. I will indemnify and hold harmless BidVex Inc., its officers, directors, employees, contractors, affiliates, and shareholders from any claim, lawsuit, regulatory action, fine, penalty, chargeback, fraud loss, or damage of any kind arising directly or indirectly from my activities under this agreement, INCLUDING acts or omissions of my managed buyers.</p>
        <p>This liability is uncapped, non-waivable, and survives termination of my broker account on the platform.</p>
      </>
    ),
    s1_check:     'I accept Section 1 — Unlimited Personal Liability.',
    s2_title:     'Section 2 — Platform Immunity',
    s2_text: (
      <>
        <p>I acknowledge that BidVex Inc. operates strictly as a digital marketplace platform — a software intermediary that connects buyers, sellers, and licensed brokers. BidVex IS NOT a dealer, auctioneer, broker, insurer, escrow agent, title transfer agent, regulator, lender, or financial intermediary.</p>
        <p>I will not initiate, support, finance, or participate in any lawsuit, class action, arbitration, mediation, regulatory complaint, or public defamation campaign against BidVex Inc., its parent companies, or affiliates with respect to: vehicle quality, condition, accident history, lien status, title fraud, mileage discrepancy, repossession risk, buyer default, seller misrepresentation, financing failure, insurance gap, taxation issue, shipping damage, storage default, currency exchange, dispute outcomes, or any business dispute originating from a BidVex transaction.</p>
        <p>I waive any right to file such an action against BidVex and irrevocably consent to binding mediation in Sherbrooke, Québec for any platform-fee-related dispute.</p>
      </>
    ),
    s2_check:     'I accept Section 2 — BidVex Platform Immunity & Waiver.',
    s3_title:     'Section 3 — Data, Audit & Consent',
    s3_text: (
      <>
        <p>I consent to BidVex retaining all of my broker bids, buyer relationship records, KYC documents, deposit holds, refund actions, invoices, signed contracts, IP addresses, device user-agents, and platform communications in an immutable, append-only audit ledger for at least seven (7) years, as required by Canadian commercial record retention law.</p>
        <p>I consent to BidVex disclosing these records to any competent provincial or federal regulator (including OMVIC, OPC, SAAQ, AMVIC, VSA, FINTRAC, CRA, RQ), law-enforcement agency, court order, or auditor — without prior notification to me — when a formal request is received.</p>
        <p>I will keep the proprietary data and unique buyer information I receive through BidVex confidential, and I will not poach buyers off-platform during the term of this agreement and for twelve (12) months after termination.</p>
      </>
    ),
    s3_check:     'I accept Section 3 — Audit, Data Retention & Non-Solicitation.',
    signature_label: 'Type your full legal name as your digital signature',
    signature_hint:  'Must match the legal name on your broker licence.',
    accept_btn:   'Accept & Sign Agreement',
    cancel_btn:   'Cancel',
    locked_msg:   'Please scroll to the bottom and accept all three sections to enable the signature field.',
    success:      'Liability agreement signed successfully.',
  },
  fr: {
    title:        'Accord de responsabilité du courtier',
    subtitle:     'Vous devez faire défiler les trois sections et accepter chacune avant de signer.',
    scroll_hint:  'Faites défiler jusqu\'en bas pour activer le champ de signature.',
    s1_title:     'Section 1 — Acceptation totale (100 %) de la responsabilité',
    s1_text: (
      <>
        <p>Je, soussigné, courtier licencié, accepte par les présentes la PLEINE ET EXCLUSIVE RESPONSABILITÉ LÉGALE pour toute interaction, communication, transaction, mise, contrat, règlement, remise de véhicule, transfert de titre et litige après-vente qui survient entre tout acheteur que je gère sur la plateforme BidVex et tout vendeur, concessionnaire, encanteur, partenaire, installation ou tiers.</p>
        <p>Je confirme détenir toutes les inscriptions provinciales et cautions requises et que ma licence demeure en règle. Je m\'engage à indemniser et à dégager de toute responsabilité BidVex Inc., ses dirigeants, administrateurs, employés, sous-traitants, sociétés affiliées et actionnaires de toute réclamation, poursuite, action réglementaire, amende, pénalité, rétrofacturation, perte par fraude ou dommage de toute nature découlant directement ou indirectement de mes activités en vertu du présent accord, Y COMPRIS les actes ou omissions des acheteurs que je gère.</p>
        <p>Cette responsabilité est illimitée, ne peut faire l\'objet d\'aucune renonciation et survit à la résiliation de mon compte de courtier sur la plateforme.</p>
      </>
    ),
    s1_check:     'J\'accepte la Section 1 — Responsabilité personnelle illimitée.',
    s2_title:     'Section 2 — Immunité de la plateforme',
    s2_text: (
      <>
        <p>Je reconnais que BidVex Inc. fonctionne strictement comme une plateforme de marché numérique — un intermédiaire logiciel qui connecte les acheteurs, les vendeurs et les courtiers licenciés. BidVex N\'EST PAS un concessionnaire, encanteur, courtier, assureur, agent de dépôt fiduciaire, agent de transfert de titre, régulateur, prêteur ou intermédiaire financier.</p>
        <p>Je n\'engagerai, ne soutiendrai, ne financerai ni ne participerai à aucune poursuite, action collective, arbitrage, médiation, plainte réglementaire ou campagne de diffamation publique contre BidVex Inc., ses sociétés mères ou ses sociétés affiliées concernant : la qualité, l\'état, l\'historique d\'accident, le statut du privilège, la fraude de titre, l\'écart de kilométrage, le risque de reprise, le défaut de l\'acheteur, la fausse représentation du vendeur, l\'échec du financement, le manque d\'assurance, les problèmes fiscaux, les dommages d\'expédition, le défaut d\'entreposage, le change de devises, les résultats de litige ou tout différend commercial provenant d\'une transaction BidVex.</p>
        <p>Je renonce à tout droit d\'intenter une telle action contre BidVex et consens irrévocablement à une médiation exécutoire à Sherbrooke, Québec, pour tout litige relatif aux frais de plateforme.</p>
      </>
    ),
    s2_check:     'J\'accepte la Section 2 — Immunité et renonciation de la plateforme BidVex.',
    s3_title:     'Section 3 — Données, audit et consentement',
    s3_text: (
      <>
        <p>Je consens à ce que BidVex conserve toutes mes mises de courtier, dossiers de relation avec les acheteurs, documents KYC, retenues de dépôt, actions de remboursement, factures, contrats signés, adresses IP, agents utilisateurs d\'appareils et communications de plateforme dans un registre d\'audit immuable et en ajout uniquement pendant au moins sept (7) ans, conformément à la loi canadienne sur la conservation des dossiers commerciaux.</p>
        <p>Je consens à ce que BidVex divulgue ces dossiers à tout régulateur provincial ou fédéral compétent (y compris OMVIC, OPC, SAAQ, AMVIC, VSA, CANAFE, ARC, RQ), agence d\'application de la loi, ordonnance du tribunal ou auditeur — sans préavis — lorsqu\'une demande formelle est reçue.</p>
        <p>Je garderai confidentielles les données exclusives et les informations uniques sur les acheteurs que je reçois par l\'intermédiaire de BidVex, et je ne débaucherai pas d\'acheteurs hors plateforme pendant la durée du présent accord et pendant douze (12) mois après la résiliation.</p>
      </>
    ),
    s3_check:     'J\'accepte la Section 3 — Audit, conservation des données et non-sollicitation.',
    signature_label: 'Tapez votre nom légal complet comme signature numérique',
    signature_hint:  'Doit correspondre au nom légal sur votre permis de courtier.',
    accept_btn:   'Accepter et signer',
    cancel_btn:   'Annuler',
    locked_msg:   'Veuillez faire défiler jusqu\'au bas et accepter les trois sections pour activer le champ de signature.',
    success:      'Accord de responsabilité signé avec succès.',
  },
};

export default function BrokerLiabilityAgreementModal({ open, onClose, onSigned, lang = 'en' }) {
  const t = COPY[lang === 'fr' ? 'fr' : 'en'];

  const scrollRef = useRef(null);
  const [scrolledBottom, setScrolledBottom] = useState(false);
  const [section1, setSection1] = useState(false);
  const [section2, setSection2] = useState(false);
  const [section3, setSection3] = useState(false);
  const [signature, setSignature] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [doneFlash, setDoneFlash] = useState(false);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setScrolledBottom(false); setSection1(false); setSection2(false); setSection3(false);
      setSignature(''); setError(null); setDoneFlash(false);
      // Scroll back to top for next open
      if (scrollRef.current) scrollRef.current.scrollTop = 0;
    }
  }, [open]);

  const onScroll = (e) => {
    const el = e.currentTarget;
    // 24px tolerance because of rounding / sub-pixel devices
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 24) {
      setScrolledBottom(true);
    }
  };

  const allAccepted = section1 && section2 && section3;
  const canSign = scrolledBottom && allAccepted && signature.trim().length >= 2;

  const submit = async () => {
    if (!canSign || submitting) return;
    setSubmitting(true); setError(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const r = await axios.post(
        `${API_BASE}/brokers/sign-liability`,
        {
          signature_full_name: signature.trim(),
          accepted_section_1:  section1,
          accepted_section_2:  section2,
          accepted_section_3:  section3,
          scrolled_to_bottom:  scrolledBottom,
          locale:              lang,
        },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.data?.success) {
        setDoneFlash(true);
        if (onSigned) onSigned(r.data);
        setTimeout(() => { if (onClose) onClose(); }, 1100);
      }
    } catch (e) {
      setError(
        e?.response?.data?.detail?.[lang === 'fr' ? 'message_fr' : 'message_en']
        || e?.response?.data?.detail?.error
        || (lang === 'fr' ? 'La signature a échoué.' : 'Signature failed.')
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
      data-testid="liability-agreement-modal"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white dark:bg-slate-900 w-full max-w-2xl rounded-xl shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
        {/* Header */}
        <header className="px-5 py-3 border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <Scale className="w-5 h-5 flex-shrink-0" />
            <h2 className="font-bold text-base sm:text-lg truncate">{t.title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 rounded-md hover:bg-white/20 transition disabled:opacity-50"
            aria-label="Close"
            data-testid="liability-modal-close"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        {/* Sub-header / hint */}
        <div className="px-5 py-2.5 bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs flex items-center gap-2">
          <ScrollText className="w-4 h-4 flex-shrink-0" />
          <span>{t.subtitle}</span>
        </div>

        {/* Scrollable legal body */}
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="flex-1 overflow-y-auto px-5 py-4 space-y-5 text-sm leading-relaxed text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-900/40"
          data-testid="liability-scroll-container"
        >
          <Section icon={ShieldAlert} title={t.s1_title} accent="rose">{t.s1_text}</Section>
          <label className="flex items-start gap-3 p-3 rounded-lg border-2 border-rose-200 dark:border-rose-800 bg-white dark:bg-slate-800 cursor-pointer">
            <input type="checkbox" checked={section1} onChange={(e) => setSection1(e.target.checked)} className="mt-1 h-5 w-5 accent-rose-600" data-testid="liability-check-1" />
            <span className="font-semibold text-rose-700 dark:text-rose-300">{t.s1_check}</span>
          </label>

          <Section icon={Lock} title={t.s2_title} accent="blue">{t.s2_text}</Section>
          <label className="flex items-start gap-3 p-3 rounded-lg border-2 border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-800 cursor-pointer">
            <input type="checkbox" checked={section2} onChange={(e) => setSection2(e.target.checked)} className="mt-1 h-5 w-5 accent-blue-600" data-testid="liability-check-2" />
            <span className="font-semibold text-blue-700 dark:text-blue-300">{t.s2_check}</span>
          </label>

          <Section icon={ScrollText} title={t.s3_title} accent="emerald">{t.s3_text}</Section>
          <label className="flex items-start gap-3 p-3 rounded-lg border-2 border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-800 cursor-pointer">
            <input type="checkbox" checked={section3} onChange={(e) => setSection3(e.target.checked)} className="mt-1 h-5 w-5 accent-emerald-600" data-testid="liability-check-3" />
            <span className="font-semibold text-emerald-700 dark:text-emerald-300">{t.s3_check}</span>
          </label>

          <div className="text-xs text-slate-400 text-center py-2" data-testid="liability-bottom-sentinel">— end of agreement —</div>
        </div>

        {/* Scroll hint until reached */}
        {!scrolledBottom && (
          <div className="px-5 py-2 bg-slate-100 dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 flex items-center gap-2" data-testid="liability-scroll-hint">
            <ChevronDown className="w-4 h-4 animate-bounce text-amber-600" />
            <span>{t.scroll_hint}</span>
          </div>
        )}

        {/* Signature + footer */}
        <footer className="px-5 py-4 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 space-y-3">
          {error && (
            <Alert variant="destructive" data-testid="liability-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{String(error)}</AlertDescription>
            </Alert>
          )}
          {doneFlash && (
            <Alert className="border-emerald-300 bg-emerald-50">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <AlertDescription className="text-emerald-800">{t.success}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
              {t.signature_label} <span className="text-rose-500">*</span>
            </label>
            <Input
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
              placeholder={lang === 'fr' ? 'Prénom Nom' : 'Full Legal Name'}
              disabled={!scrolledBottom || !allAccepted || submitting}
              data-testid="liability-signature-input"
              className="font-serif italic text-lg"
            />
            <p className="text-[11px] text-slate-500">{t.signature_hint}</p>
          </div>
          {!canSign && (
            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5" data-testid="liability-locked-msg">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>{t.locked_msg}</span>
            </p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose} disabled={submitting} data-testid="liability-cancel">
              {t.cancel_btn}
            </Button>
            <Button
              onClick={submit}
              disabled={!canSign || submitting}
              className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
              data-testid="liability-submit"
            >
              {submitting ? '…' : t.accept_btn}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function Section({ icon: Icon, title, children, accent = 'slate' }) {
  const accentMap = {
    rose:    'border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300',
    blue:    'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300',
    emerald: 'border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300',
    slate:   'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200',
  };
  return (
    <div className={`rounded-lg border-2 ${accentMap[accent]} px-4 py-3`}>
      <h3 className="font-bold mb-2 flex items-center gap-2">
        <Icon className="w-4 h-4 flex-shrink-0" />
        {title}
      </h3>
      <div className="space-y-2 text-sm text-slate-700 dark:text-slate-200">{children}</div>
    </div>
  );
}
