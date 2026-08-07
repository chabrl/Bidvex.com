/**
 * StorageBulkReviewTable — iter446
 *
 * Renders the storage-unit CSV preview as an inline-editable table.
 * Each cell shows its bilingual error pill(s) directly below the input
 * so the facility sees exactly what to fix without leaving the row.
 *
 * Cross-batch and cross-facility duplicate errors surface on the
 * `unit_number` cell with a link-style hint to the conflicting listing
 * ID when the conflict is against a real open auction.
 *
 * The parent owns the rows[] state; this component emits
 * `onChange(rowIdx, field, value)` for every edit. The parent decides
 * when to re-run validation (typically on server confirm).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CheckCircle2, ExternalLink } from 'lucide-react';

const UNIT_SIZES = ['5x5', '5x10', '10x10', '10x15', '10x20', '10x30+'];
const UNIT_TYPES = ['indoor', 'outdoor', 'climate_controlled', 'drive_up'];
const PAYMENT_METHODS = ['stripe', 'cash', 'etransfer'];
const CURRENCIES = ['CAD', 'USD'];
const DEPOSIT_TYPES = ['fixed', 'percentage'];

const ErrorPill = ({ err, isFr }) => (
  <div
    className="mt-1 text-[11px] leading-tight rounded bg-red-50 text-red-700 border border-red-200 px-1.5 py-0.5"
    data-testid={`bulk-err-${err.row}-${err.field}-${err.code}`}
  >
    {isFr ? err.message_fr : err.message_en}
    {err.conflict_auction_id ? (
      <a
        href={`/storage-auctions/${err.conflict_auction_id}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-0.5 ml-1 underline hover:text-red-900"
      >
        <ExternalLink className="h-3 w-3" />
        #{String(err.conflict_auction_id).slice(0, 8)}
      </a>
    ) : null}
  </div>
);

export const StorageBulkReviewTable = ({ rows, onChange, isFr }) => {
  const { t } = useTranslation();
  const errsFor = (row, field) =>
    (row.errors || []).filter((e) => e.field === field);
  const rowHasErrors = (row) => (row.errors || []).length > 0;

  const inputCls = (r, f) =>
    `w-full px-1.5 py-1 rounded border text-xs ${
      errsFor(r, f).length ? 'border-red-400 bg-red-50/40' : 'border-slate-200'
    }`;

  return (
    <div
      className="overflow-x-auto border border-slate-200 rounded-lg"
      data-testid="storage-bulk-review-table"
    >
      <table className="min-w-full text-xs">
        <thead className="bg-slate-100 sticky top-0 z-10">
          <tr>
            <th className="px-2 py-2 text-left font-semibold">#</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[130px]">unit_number</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[100px]">unit_size</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[130px]">unit_type</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[80px]">lien</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">past_due</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[220px]">description_en</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[220px]">description_fr</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">starting_price</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">reserve</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[90px]">bid_inc</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[170px]">start_time</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[170px]">end_time</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[90px]">cleanup_h</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">payment</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[90px]">currency</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[80px]">deposit</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[110px]">deposit_amt</th>
            <th className="px-2 py-2 text-left font-semibold min-w-[120px]">deposit_type</th>
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
                data-testid={`storage-bulk-row-${r.row}`}
              >
                <td className="px-2 py-2 align-top font-mono font-semibold text-slate-500">
                  {r.row}
                  {bad ? (
                    <AlertTriangle className="h-3 w-3 text-red-500 inline ml-1" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500 inline ml-1" />
                  )}
                </td>

                {/* unit_number */}
                <td className="px-2 py-2 align-top">
                  <input
                    className={inputCls(r, 'unit_number')}
                    value={norm.unit_number || ''}
                    onChange={(e) => onChange(idx, 'unit_number', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-unit_number`}
                  />
                  {errsFor(r, 'unit_number').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* unit_size */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'unit_size')}
                    value={norm.unit_size || ''}
                    onChange={(e) => onChange(idx, 'unit_size', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-unit_size`}
                  >
                    <option value="">—</option>
                    {UNIT_SIZES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  {errsFor(r, 'unit_size').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* unit_type */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'unit_type')}
                    value={norm.unit_type || ''}
                    onChange={(e) => onChange(idx, 'unit_type', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-unit_type`}
                  >
                    <option value="">—</option>
                    {UNIT_TYPES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                  {errsFor(r, 'unit_type').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* is_lien_unit */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'is_lien_unit')}
                    value={norm.is_lien_unit ? 'Y' : 'N'}
                    onChange={(e) =>
                      onChange(idx, 'is_lien_unit', e.target.value === 'Y')
                    }
                    data-testid={`storage-bulk-input-${r.row}-is_lien_unit`}
                  >
                    <option value="N">N</option>
                    <option value="Y">Y</option>
                  </select>
                </td>

                {/* past_due_balance */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={inputCls(r, 'past_due_balance')}
                    value={norm.past_due_balance ?? ''}
                    onChange={(e) => onChange(idx, 'past_due_balance', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-past_due_balance`}
                  />
                  {errsFor(r, 'past_due_balance').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* description_en */}
                <td className="px-2 py-2 align-top">
                  <textarea
                    rows={2}
                    className={inputCls(r, 'description_en')}
                    value={norm.description_en || ''}
                    onChange={(e) => onChange(idx, 'description_en', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-description_en`}
                  />
                  {errsFor(r, 'description_en').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* description_fr */}
                <td className="px-2 py-2 align-top">
                  <textarea
                    rows={2}
                    className={inputCls(r, 'description_fr')}
                    value={norm.description_fr || ''}
                    onChange={(e) => onChange(idx, 'description_fr', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-description_fr`}
                  />
                  {errsFor(r, 'description_fr').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* starting_price */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={inputCls(r, 'starting_price')}
                    value={norm.starting_price ?? ''}
                    onChange={(e) => onChange(idx, 'starting_price', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-starting_price`}
                  />
                  {errsFor(r, 'starting_price').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* reserve_price */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={inputCls(r, 'reserve_price')}
                    value={norm.reserve_price ?? ''}
                    onChange={(e) => onChange(idx, 'reserve_price', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-reserve_price`}
                  />
                  {errsFor(r, 'reserve_price').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* bid_increment */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="1"
                    className={inputCls(r, 'bid_increment')}
                    value={norm.bid_increment ?? ''}
                    onChange={(e) => onChange(idx, 'bid_increment', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-bid_increment`}
                  />
                  {errsFor(r, 'bid_increment').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* start_time */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="datetime-local"
                    className={inputCls(r, 'start_time')}
                    value={(norm.start_time || '').slice(0, 16)}
                    onChange={(e) =>
                      onChange(idx, 'start_time', e.target.value ? `${e.target.value}:00Z` : '')
                    }
                    data-testid={`storage-bulk-input-${r.row}-start_time`}
                  />
                  {errsFor(r, 'start_time').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* end_time */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="datetime-local"
                    className={inputCls(r, 'end_time')}
                    value={(norm.end_time || '').slice(0, 16)}
                    onChange={(e) =>
                      onChange(idx, 'end_time', e.target.value ? `${e.target.value}:00Z` : '')
                    }
                    data-testid={`storage-bulk-input-${r.row}-end_time`}
                  />
                  {errsFor(r, 'end_time').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* cleanup_deadline_hours */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    min="24"
                    max="168"
                    className={inputCls(r, 'cleanup_deadline_hours')}
                    value={norm.cleanup_deadline_hours ?? ''}
                    onChange={(e) =>
                      onChange(idx, 'cleanup_deadline_hours', e.target.value)
                    }
                    data-testid={`storage-bulk-input-${r.row}-cleanup_deadline_hours`}
                  />
                  {errsFor(r, 'cleanup_deadline_hours').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* payment_method */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'payment_method')}
                    value={norm.payment_method || 'stripe'}
                    onChange={(e) => onChange(idx, 'payment_method', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-payment_method`}
                  >
                    {PAYMENT_METHODS.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  {errsFor(r, 'payment_method').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* currency */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'currency')}
                    value={norm.currency || 'CAD'}
                    onChange={(e) => onChange(idx, 'currency', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-currency`}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  {errsFor(r, 'currency').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* deposit_required */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'deposit_required')}
                    value={norm.deposit_required ? 'Y' : 'N'}
                    onChange={(e) =>
                      onChange(idx, 'deposit_required', e.target.value === 'Y')
                    }
                    data-testid={`storage-bulk-input-${r.row}-deposit_required`}
                  >
                    <option value="N">N</option>
                    <option value="Y">Y</option>
                  </select>
                </td>

                {/* deposit_amount */}
                <td className="px-2 py-2 align-top">
                  <input
                    type="number"
                    step="0.01"
                    className={inputCls(r, 'deposit_amount')}
                    value={norm.deposit_amount ?? ''}
                    onChange={(e) => onChange(idx, 'deposit_amount', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-deposit_amount`}
                  />
                  {errsFor(r, 'deposit_amount').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>

                {/* deposit_type */}
                <td className="px-2 py-2 align-top">
                  <select
                    className={inputCls(r, 'deposit_type')}
                    value={norm.deposit_type || ''}
                    onChange={(e) => onChange(idx, 'deposit_type', e.target.value)}
                    data-testid={`storage-bulk-input-${r.row}-deposit_type`}
                  >
                    <option value="">—</option>
                    {DEPOSIT_TYPES.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  {errsFor(r, 'deposit_type').map((e, i) => (
                    <ErrorPill key={i} err={e} isFr={isFr} />
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default StorageBulkReviewTable;
