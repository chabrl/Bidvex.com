/**
 * iter261 Mission 1 — Pending Payments dashboard card.
 *
 * Hits `GET /api/my/payment-requests` and surfaces every outstanding,
 * non-expired admin-issued payment request the user owes. Renders at
 * the top of the dashboard above other content so the user can't miss
 * an open balance.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CreditCard, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { useAuth } from '../contexts/AuthContext';
import API_BASE from '../config';

const fmtMoney = (n) => `$${Number(n || 0).toFixed(2)} CAD`;

const fmtShortDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-CA', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  } catch { return iso; }
};

const PendingPaymentsCard = () => {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    try {
      const r = await axios.get(`${API_BASE}/my/payment-requests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(Array.isArray(r.data?.items) ? r.data.items : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  if (loading || !token) return null;

  if (items.length === 0) {
    return (
      <Card className="mb-4" data-testid="pending-payments-empty-card">
        <CardContent className="py-4 text-center text-xs text-slate-500">
          ✅ No pending payments. You're all clear!
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className="mb-6"
      style={{ border: '1.5px solid #fed7d7', borderRadius: 10, backgroundColor: '#fff5f5' }}
      data-testid="pending-payments-card"
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base flex items-center gap-2 text-slate-900">
          <CreditCard className="h-5 w-5 text-[#e53e3e]" />
          💳 Pending Payments
        </CardTitle>
        <Badge
          style={{
            backgroundColor: '#fff0f0', color: '#e53e3e',
            border: '1px solid #fed7d7', borderRadius: 4,
            padding: '2px 8px', fontWeight: 700, fontSize: 11,
          }}
        >
          {items.length} pending
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 pt-2">
        {items.map((p) => (
          <div
            key={p.id}
            className="border-t border-rose-200 pt-3 first:border-t-0 first:pt-0"
            data-testid={`pending-payment-row-${p.id}`}
          >
            <div className="flex items-start justify-between gap-3 mb-1">
              <div className="flex-1 min-w-0">
                <p
                  className="font-bold text-base"
                  style={{ color: '#e53e3e', fontWeight: 700 }}
                  data-testid={`pending-payment-amount-${p.id}`}
                >
                  {fmtMoney(p.total_amount)}
                </p>
                <p className="text-sm text-slate-700 truncate">— {p.description || 'Outstanding balance'}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Requested: {fmtShortDate(p.created_at)}
                  {p.expires_at && (<> · Expires: {fmtShortDate(p.expires_at)}</>)}
                </p>
              </div>
              <Badge
                style={{
                  backgroundColor: '#fff0f0', color: '#e53e3e',
                  border: '1px solid #fed7d7', borderRadius: 4,
                  padding: '2px 8px', fontWeight: 700, fontSize: 11,
                  flexShrink: 0,
                }}
              >
                PENDING
              </Badge>
            </div>
            <a
              href={p.payment_url}
              className="inline-flex items-center gap-1 mt-1 font-bold text-sm"
              style={{
                backgroundColor: '#0055FF', color: 'white',
                borderRadius: 6, padding: '8px 18px', textDecoration: 'none',
              }}
              data-testid={`pending-payment-pay-now-${p.id}`}
            >
              Pay Now <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default PendingPaymentsCard;
