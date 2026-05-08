/**
 * iter201 — Phase 2 — Province-aware seller notice.
 *
 * Loads a single province_regulations doc from the backend and renders the
 * seller-side notice (license type, regulatory body, additional requirements,
 * tax structure). Use inside the seller wizard / listing form to dynamically
 * show the dealer obligations for the seller's chosen province.
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Shield, Loader2, AlertTriangle, Globe2 } from 'lucide-react';

const API = API_BASE;

const ProvinceSellerNotice = ({ provinceCode }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!provinceCode) { setDoc(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await axios.get(`${API}/vehicles/province-regulations/${provinceCode}`);
        if (!cancelled) setDoc(res.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || 'Unknown province');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [provinceCode]);

  if (!provinceCode) return null;
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="province-seller-notice-loading">
        <Loader2 className="h-4 w-4 animate-spin" />
        {isFr ? 'Chargement des règlements provinciaux…' : 'Loading provincial regulations…'}
      </div>
    );
  }
  if (error || !doc) {
    return (
      <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" data-testid="province-seller-notice-error">
        <AlertTriangle className="inline h-3.5 w-3.5 mr-1" /> {error}
      </div>
    );
  }

  const labelLicense = isFr ? doc.license_type_fr : doc.license_type_en;
  const noticeText = isFr ? doc.seller_notice_fr : doc.seller_notice_en;
  const reqs = isFr ? doc.additional_requirements_fr : doc.additional_requirements_en;
  const provinceName = isFr ? doc.province_name_fr : doc.province_name_en;

  // Tax breakdown display
  const tx = doc.tax_rates || {};
  const taxParts = [];
  if (tx.GST) taxParts.push(`GST ${(tx.GST * 100).toFixed(0)}%`);
  if (tx.PST_QST) taxParts.push(`${doc.province_code === 'QC' ? 'QST' : 'PST'} ${(tx.PST_QST * 100).toFixed(2)}%`);
  if (tx.HST) taxParts.push(`HST ${(tx.HST * 100).toFixed(0)}%`);
  const taxLine = taxParts.join(' + ') || (isFr ? 'Sans taxe applicable' : 'No applicable tax');

  return (
    <div
      className="rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-4"
      data-testid="province-seller-notice"
    >
      <div className="flex items-start gap-3">
        <Shield className="h-5 w-5 text-blue-600 dark:text-blue-300 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-blue-700 dark:text-blue-300 uppercase tracking-wider">
            {provinceName} · {doc.regulatory_body}
          </p>
          <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mt-0.5" data-testid="province-seller-notice-license-type">
            {labelLicense}
          </p>
          <p className="text-sm text-blue-800 dark:text-blue-200 mt-2 leading-relaxed">{noticeText}</p>

          {Array.isArray(reqs) && reqs.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-blue-800/90 dark:text-blue-200/90 list-disc list-inside">
              {reqs.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px]">
            <span className="bg-white dark:bg-slate-900 border border-blue-200 dark:border-blue-700 rounded px-2 py-0.5 text-blue-700 dark:text-blue-300 font-mono">
              {taxLine}
            </span>
            {doc.requires_bilingual_listings && (
              <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 border border-amber-300 rounded px-2 py-0.5 font-semibold">
                <Globe2 className="h-3 w-3" />
                {isFr ? 'Annonce bilingue requise' : 'Bilingual listing required'}
              </span>
            )}
            {doc.requires_admin_review && (
              <span className="bg-purple-100 text-purple-800 border border-purple-300 rounded px-2 py-0.5 font-semibold">
                {isFr ? 'Examen manuel BidVex' : 'Manual BidVex review'}
              </span>
            )}
            {doc.license_verification_url && (
              <a
                href={doc.license_verification_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-700 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200 underline-offset-2 hover:underline"
                data-testid="province-seller-notice-verify-url"
              >
                {isFr ? 'Vérifier le permis' : 'Verify licence'} ↗
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProvinceSellerNotice;
