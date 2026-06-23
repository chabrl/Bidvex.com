/**
 * iter313 — Universal Save-as-Draft button.
 *
 * Drop this into ANY of the 5 listing creation wizards. It hits the new
 * POST /api/drafts/save endpoint which accepts partial / half-typed
 * form data without strict validation. On success it stores the
 * returned draft_id in formData (caller responsibility) so subsequent
 * clicks update the same draft in place.
 *
 * iter313 patch (Feb 22, 2026): The button now renders as a fixed
 * floating affordance at the top-right of the viewport via React
 * portal, with z-[90] so it stays clickable above the
 * TaxInterviewModal overlay (z-[70]) and the navbar (z-[80]). This
 * fulfils the P0 directive: "Save as Draft must work at every step of
 * every wizard" — including the half-typed pre-tax-onboarding state.
 *
 * Props:
 *   - type:         "marketplace" | "lots" | "storage" | "vehicle" | "multi_lot_vehicle"
 *   - formData:     object — the current wizard form snapshot
 *   - draftId:      string | null — the existing draft id (for updates)
 *   - onSaved:      (draftId, expiresInDays) => void — caller wires this
 *                     to update its formData.draft_id state
 *   - className:    optional extra Tailwind classes
 *   - testid:       optional override; defaults to `save-as-draft-btn-${type}`
 */
import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const SaveAsDraftButton = ({
  type,
  formData,
  draftId,
  onSaved,
  className = '',
  testid,
}) => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      // Strip File objects & circular refs by JSON.parse(JSON.stringify(...))
      // since formData often contains nested non-serializable values.
      let payload;
      try { payload = JSON.parse(JSON.stringify(formData || {})); }
      catch { payload = { ...(formData || {}) }; }

      const r = await axios.post(`${API_BASE}/drafts/save`, {
        type,
        draft_id: draftId || null,
        payload,
      });
      const id = r.data?.draft_id;
      const days = r.data?.expires_in_days;
      toast.success(
        fr
          ? `Brouillon enregistré (expire dans ${days} jours).`
          : `Draft saved (expires in ${days} days).`
      );
      if (typeof onSaved === 'function' && id) {
        onSaved(id, days);
      }
    } catch (err) {
      toast.error(
        (err?.response?.data?.detail?.message_en) ||
        (typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : null) ||
        (fr ? 'Échec de l\'enregistrement du brouillon' : 'Failed to save draft')
      );
    } finally {
      setSaving(false);
    }
  };

  const button = (
    <button
      type="button"
      onClick={handleSave}
      disabled={saving}
      className={`fixed top-20 right-4 z-[90] px-4 py-2 rounded-full border border-amber-400 bg-amber-50 text-amber-900 hover:bg-amber-100 text-sm font-semibold shadow-lg disabled:opacity-50 transition ${className}`}
      data-testid={testid || `save-as-draft-btn-${type}`}
    >
      {saving
        ? (fr ? 'Enregistrement…' : 'Saving…')
        : (fr ? 'Enregistrer comme brouillon' : 'Save as Draft')
      }
    </button>
  );

  // Render into document.body via portal so the fixed-position button
  // escapes any parent stacking context (modals, sticky headers, etc.)
  if (typeof document === 'undefined' || !document.body) return button;
  return createPortal(button, document.body);
};

export default SaveAsDraftButton;
