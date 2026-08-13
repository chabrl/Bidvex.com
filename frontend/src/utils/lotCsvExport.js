/**
 * iter482+ — Canonical Lot CSV Export helper (frontend)
 * =====================================================
 *
 * All UI surfaces (SellerDashboard, MultiItemListingDetailPage,
 * ManageAllAuctions) route through this single helper to keep the
 * fetch → Blob → download pattern identical everywhere.  The backend
 * is the single source of truth — this helper only handles the
 * browser mechanics.
 *
 * Usage
 * -----
 *
 *   await downloadLotCsv({
 *     auctionId: 'auc-123',
 *     surface: 'seller' | 'public' | 'admin',
 *     token,                       // required for seller & admin
 *     apiBase,                     // typically REACT_APP_BACKEND_URL + '/api'
 *     lang: 'en' | 'fr',
 *     onSuccess: () => toast.success(...),
 *     onError:   (err) => toast.error(...),
 *   });
 */

export async function downloadLotCsv({
  auctionId,
  surface,
  token,
  apiBase,
  lang = 'en',
  includeDrafts = false,
  onSuccess,
  onError,
}) {
  const fr = String(lang || 'en').startsWith('fr');
  try {
    const params = new URLSearchParams({ surface });
    if (includeDrafts) params.set('include_drafts', 'true');
    const url = `${apiBase}/exports/lots/${encodeURIComponent(auctionId)}?${params.toString()}`;

    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(url, { headers });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }

    // Extract filename from Content-Disposition (backend-controlled)
    const cd = res.headers.get('content-disposition') || '';
    const m = /filename="?([^";]+)"?/i.exec(cd);
    const filename = (m && m[1]) || `bidvex_lots_${auctionId}_${surface}.csv`;

    const blob = await res.blob();
    const dl = document.createElement('a');
    dl.href = URL.createObjectURL(blob);
    dl.download = filename;
    document.body.appendChild(dl);
    dl.click();
    dl.remove();
    URL.revokeObjectURL(dl.href);

    if (typeof onSuccess === 'function') onSuccess({ filename, size: blob.size });
    return { filename, size: blob.size };
  } catch (err) {
    if (typeof onError === 'function') {
      onError(err, {
        genericMessage: fr ? 'Échec de l\u2019exportation CSV' : 'CSV export failed',
      });
    }
    throw err;
  }
}

/**
 * Localised toast messages for the three surfaces.  Callers can
 * reuse these strings so wording stays consistent everywhere.
 */
export const CSV_LOCALES = {
  en: {
    downloading:  'Preparing CSV export…',
    success:      'CSV export downloaded',
    failed:       'CSV export failed',
    guestBlocked: 'Sign in to download the lot list',
  },
  fr: {
    downloading:  'Préparation de l\u2019exportation CSV…',
    success:      'Exportation CSV téléchargée',
    failed:       'Échec de l\u2019exportation CSV',
    guestBlocked: 'Connectez-vous pour télécharger la liste des lots',
  },
};

export function csvLocale(lang) {
  return String(lang || 'en').startsWith('fr')
    ? CSV_LOCALES.fr
    : CSV_LOCALES.en;
}
