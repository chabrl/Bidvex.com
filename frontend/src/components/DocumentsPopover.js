/**
 * iter474 — Documents popover for a paid purchase (buyer) or sale (seller).
 *
 * Behaviour:
 *   • On open, fetches `/api/dashboard/documents/{purchase|sale}` for the
 *     current row and renders one entry per document kind.
 *   • Shows the current-language label. For multi-lot orders the invoice
 *     is labelled "Order Invoice" / "Facture de commande" and the seller
 *     statement is labelled "Settlement Statement" / "Relevé de règlement".
 *   • Downloads happen via the signed URL returned by the backend — never
 *     a raw internal API path. If a document is unsupported for the
 *     section the row is disabled with a bilingual "Not available yet"
 *     hint (no auto-email is triggered, no new document type invented).
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import API_BASE from '../config';
import { Button } from './ui/button';
import { FileText, Download, Info, Loader2 } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from './ui/popover';

const API = API_BASE;

// Label lookup: keyed by `label_key` returned by the backend so the
// bilingual copy stays with the frontend and the API stays language-
// neutral. Falls back to a generic label if the backend adds a new key.
const LABELS = {
  invoice:              { en: 'Download Invoice',              fr: 'Télécharger la facture' },
  order_invoice:        { en: 'Download Order Invoice',        fr: 'Télécharger la facture de commande' },
  payment_letter:       { en: 'Download Payment Letter',       fr: 'Télécharger la lettre de paiement' },
  receipt:              { en: 'Download Receipt',              fr: 'Télécharger le reçu' },
  statement:            { en: 'Download Statement',            fr: 'Télécharger le relevé' },
  settlement_statement: { en: 'Download Settlement Statement', fr: 'Télécharger le relevé de règlement' },
  seller_receipt:       { en: 'Download Seller Receipt',       fr: 'Télécharger le reçu du vendeur' },
  commission_invoice:   { en: 'Download Commission Invoice',   fr: 'Télécharger la facture de commission' },
};

// Fixed display order per role so the popover renders deterministically
// regardless of the object-key iteration order returned by the backend.
const BUYER_ORDER = ['invoice', 'receipt', 'payment_letter'];
const SELLER_ORDER = ['statement', 'seller_receipt', 'commission_invoice'];

// Fallback label_key when a kind is unsupported (no `label_key` in the
// response). Keeps the row identifiable while it's disabled.
const FALLBACK_LABEL_KEY = {
  invoice:              'invoice',
  payment_letter:       'payment_letter',
  receipt:              'receipt',
  statement:            'statement',
  seller_receipt:       'seller_receipt',
  commission_invoice:   'commission_invoice',
};

/**
 * @param {'purchase' | 'sale'} role  which side of the transaction
 * @param {string} section            marketplace | lots | vehicles | storage
 * @param {string} listingId          canonical listing id (auction id)
 * @param {number|null} lotNumber     lot number for multi-lot rows
 * @param {string} testIdSuffix       unique suffix for `data-testid`
 */
export const DocumentsPopover = ({
  role, section, listingId, lotNumber = null, testIdSuffix,
}) => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);   // {documents, multi_lot, ...}
  const [error, setError] = useState(null);

  const kindsOrder = role === 'sale' ? SELLER_ORDER : BUYER_ORDER;
  const endpoint = role === 'sale'
    ? `${API}/dashboard/documents/sale`
    : `${API}/dashboard/documents/purchase`;

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { section, listing_id: listingId };
      if (lotNumber !== null && lotNumber !== undefined) params.lot_number = lotNumber;
      const r = await axios.get(endpoint, { params });
      setData(r.data);
    } catch (e) {
      if (e?.response?.status === 403) {
        setError(fr ? 'Accès non autorisé.' : 'Not authorized.');
      } else if (e?.response?.status === 400) {
        setError(fr ? 'Requête invalide.' : 'Invalid request.');
      } else {
        setError(fr ? 'Erreur de chargement.' : 'Failed to load.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (v) => {
    setOpen(v);
    if (v && !data && !loading) load();
  };

  const NOT_AVAILABLE = fr ? 'Non disponible pour le moment' : 'Not available yet';

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs rounded-full px-3"
          data-testid={`documents-btn-${testIdSuffix}`}
        >
          <FileText className="h-3.5 w-3.5 mr-1" />
          {fr ? 'Documents' : 'Documents'}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-72 p-2"
        align="end"
        data-testid={`documents-popover-${testIdSuffix}`}
      >
        {loading && (
          <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {fr ? 'Chargement…' : 'Loading…'}
          </div>
        )}

        {!loading && error && (
          <div className="flex items-start gap-2 p-3 text-sm text-red-700 dark:text-red-300">
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span data-testid={`documents-error-${testIdSuffix}`}>{error}</span>
          </div>
        )}

        {!loading && !error && data && (
          <div className="space-y-1" data-multi-lot={data.multi_lot ? 'true' : 'false'}>
            {kindsOrder.map((kind) => {
              const entry = data.documents?.[kind] || { available: false };
              const labelKey = entry.label_key || FALLBACK_LABEL_KEY[kind];
              const labelObj = LABELS[labelKey] || LABELS[FALLBACK_LABEL_KEY[kind]] || null;
              const label = labelObj ? (fr ? labelObj.fr : labelObj.en) : kind;

              if (entry.available && entry.signed_url) {
                return (
                  <a
                    key={kind}
                    href={entry.signed_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-2.5 py-2 rounded-md text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                    data-testid={`document-link-${kind}-${testIdSuffix}`}
                    data-label-key={labelKey}
                  >
                    <Download className="h-4 w-4 text-emerald-600" />
                    <span className="flex-1 truncate">{label}</span>
                    {entry.invoice_number && (
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {entry.invoice_number}
                      </span>
                    )}
                  </a>
                );
              }
              return (
                <div
                  key={kind}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-md text-sm text-muted-foreground"
                  data-testid={`document-unavailable-${kind}-${testIdSuffix}`}
                  data-label-key={labelKey}
                >
                  <Download className="h-4 w-4 opacity-40" />
                  <span className="flex-1 truncate line-through opacity-70">{label}</span>
                  <span className="text-[10px] italic flex-shrink-0">
                    {NOT_AVAILABLE}
                  </span>
                </div>
              );
            })}

            {data.multi_lot && (
              <p
                className="text-[10px] text-muted-foreground pt-2 border-t mt-1 px-1"
                data-testid={`documents-multi-lot-note-${testIdSuffix}`}
              >
                {fr
                  ? 'Ce document couvre plusieurs lots de la même commande.'
                  : 'This document covers multiple lots of the same order.'}
              </p>
            )}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default DocumentsPopover;
