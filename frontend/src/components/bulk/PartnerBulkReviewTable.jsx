/**
 * PartnerBulkReviewTable — iter444
 *
 * Renders the CSV preview payload as an inline-editable table. Each cell
 * shows its bilingual error pill(s) directly below the input so the
 * Partner sees exactly what to fix without leaving the row.
 *
 * The parent owns the rows[] state; this component emits `onChange(rowIdx,
 * field, value)` for every edit and lets the parent decide when to re-run
 * validation (typically debounced by hitting the preview endpoint again,
 * or by calling the client-side revalidator).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

const CATEGORY_HINTS = ['electronics', 'furniture', 'clothing', 'collectibles',
  'tools', 'toys', 'sports', 'vehicles', 'jewelry', 'art', 'books', 'other'];
const CONDITIONS = ['new', 'like_new', 'excellent', 'good', 'fair', 'poor', 'used'];

const ErrorPill = ({ err, isFr }) => (
  <div className="mt-1 text-[11px] leading-tight rounded bg-red-50 text-red-700 border border-red-200 px-1.5 py-0.5">
    {isFr ? err.message_fr : err.message_en}
  </div>
);

export const PartnerBulkReviewTable = ({ rows, onChange, isFr }) => {
  const { t } = useTranslation();

  const errsFor = (row, field) =>
    (row.errors || []).filter((e) => e.field === field);
  const rowHasErrors = (row) => (row.errors || []).length > 0;

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg" data-testid="bulk-review-table">
      <table className="min-w-full text-xs">
        <thead className="bg-slate-100 sticky top-0 z-10">
          <tr>
            <th className="px-2 py-2 text-left font-semibold">#</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[180px]">title</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[180px]">title_fr</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[140px]">category</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">starting_price</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[80px]">quantity</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">condition</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[180px]">auction_end_date</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[130px]">city</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[70px]">region</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[120px]">buy_now_price</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[130px]">buyers_premium_%</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => {
            const norm = r.normalized || {};
            const bad = rowHasErrors(r);
            return (
              <tr
                key={r.row}
                className={bad ? 'bg-red-50/40' : 'bg-emerald-50/20'}
                data-testid={`bulk-row-${r.row}`}
              >
                <td className="px-2 py-2 align-top font-mono font-semibold text-slate-500">
                  {r.row}
                  {bad ? (
                    <AlertTriangle className="h-3 w-3 text-red-500 inline ml-1" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500 inline ml-1" />
                  )}
                </td>

                {['title', 'title_fr'].map((f) => (
                  <td key={f} className="px-2 py-2 align-top">
                    <input
                      className={`w-full px-1.5 py-1 rounded border ${errsFor(r, f).length ? 'border-red-400' : 'border-slate-200'}`}
                      value={norm[f] || ''}
                      onChange={(e) => onChange(idx, f, e.target.value)}
                      data-testid={`bulk-input-${r.row}-${f}`}
                    />
                    {errsFor(r, f).map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                  </td>
                ))}

                <td className="px-2 py-2 align-top">
                  <input
                    list="cat-hints"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'category').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.category || ''}
                    onChange={(e) => onChange(idx, 'category', e.target.value.toLowerCase())}
                    data-testid={`bulk-input-${r.row}-category`}
                  />
                  {errsFor(r, 'category').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'starting_price').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.starting_price ?? ''}
                    onChange={(e) => onChange(idx, 'starting_price', e.target.value)}
                    data-testid={`bulk-input-${r.row}-starting_price`}
                  />
                  {errsFor(r, 'starting_price').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'quantity').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.quantity ?? ''}
                    onChange={(e) => onChange(idx, 'quantity', e.target.value)}
                    data-testid={`bulk-input-${r.row}-quantity`}
                  />
                  {errsFor(r, 'quantity').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                <td className="px-2 py-2 align-top">
                  <select
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'condition').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.condition || ''}
                    onChange={(e) => onChange(idx, 'condition', e.target.value)}
                    data-testid={`bulk-input-${r.row}-condition`}
                  >
                    <option value="">—</option>
                    {CONDITIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  {errsFor(r, 'condition').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                <td className="px-2 py-2 align-top">
                  <input
                    type="datetime-local"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'auction_end_date').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={(norm.auction_end_date || '').slice(0, 16)}
                    onChange={(e) => onChange(idx, 'auction_end_date', e.target.value ? `${e.target.value}:00Z` : '')}
                    data-testid={`bulk-input-${r.row}-auction_end_date`}
                  />
                  {errsFor(r, 'auction_end_date').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                {['city', 'region'].map((f) => (
                  <td key={f} className="px-2 py-2 align-top">
                    <input
                      className={`w-full px-1.5 py-1 rounded border ${errsFor(r, f).length ? 'border-red-400' : 'border-slate-200'}`}
                      value={norm[f] || ''}
                      onChange={(e) => onChange(idx, f, f === 'region' ? e.target.value.toUpperCase() : e.target.value)}
                      data-testid={`bulk-input-${r.row}-${f}`}
                    />
                    {errsFor(r, f).map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                  </td>
                ))}

                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'buy_now_price').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.buy_now_price ?? ''}
                    onChange={(e) => onChange(idx, 'buy_now_price', e.target.value)}
                    data-testid={`bulk-input-${r.row}-buy_now_price`}
                  />
                  {errsFor(r, 'buy_now_price').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>

                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.1"
                    className={`w-full px-1.5 py-1 rounded border ${errsFor(r, 'buyers_premium_percent').length ? 'border-red-400' : 'border-slate-200'}`}
                    value={norm.buyers_premium_percent ?? ''}
                    onChange={(e) => onChange(idx, 'buyers_premium_percent', e.target.value)}
                    data-testid={`bulk-input-${r.row}-buyers_premium_percent`}
                  />
                  {errsFor(r, 'buyers_premium_percent').map((e, i) => <ErrorPill key={i} err={e} isFr={isFr} />)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <datalist id="cat-hints">
        {CATEGORY_HINTS.map((c) => <option key={c} value={c} />)}
      </datalist>
    </div>
  );
};

export default PartnerBulkReviewTable;
