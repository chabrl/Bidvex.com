/**
 * BidVex — Phase 6.2 Task 4
 * Buyer-facing "My Cleanouts" page.
 *
 * Shows every won storage-locker invoice that has an active cleanout hold,
 * with a live countdown ticker and a "Mark Unit as Completely Cleared" CTA.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Loader2 } from 'lucide-react';

import CleanoutCountdownTicker from '../../components/CleanoutCountdownTicker';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function MyCleanoutsPage() {
  const { t } = useTranslation();
  const [holds, setHolds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submittingId, setSubmittingId] = useState(null);

  const fetchHolds = useCallback(async () => {
    setLoading(true);
    try {
      const token = window.localStorage.getItem('token');
      // Reuse the existing buyer-storage-deposits endpoint as the source of
      // won invoices. We hydrate cleanout status per-row via the new endpoint.
      const res = await axios.get(`${API}/api/storage-auctions/my-bids`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const won = (res.data?.bids || []).filter(
        (b) => b.status === 'won' && b.invoice_id,
      );
      const enriched = await Promise.all(
        won.map(async (b) => {
          try {
            const sr = await axios.get(
              `${API}/api/storage-cleanout/${b.invoice_id}/status`,
              { headers: token ? { Authorization: `Bearer ${token}` } : {} },
            );
            return { ...b, cleanout: sr.data };
          } catch (e) {
            console.debug('[cleanouts] status fetch failed:', e);
            return { ...b, cleanout: { has_hold: false } };
          }
        }),
      );
      setHolds(enriched.filter((b) => b.cleanout?.has_hold));
    } catch (e) {
      console.error('Failed to load cleanouts', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHolds();
  }, [fetchHolds]);

  const handleMarkCleared = async (invoiceId) => {
    if (!window.confirm(
      t('cleanouts.confirmMarkCleared', {
        defaultValue:
          'Confirm: have you fully cleared this unit and removed all items? An admin will physically verify before your deposit is released. Misrepresentation may result in forfeit.',
      }),
    )) {
      return;
    }
    setSubmittingId(invoiceId);
    try {
      const token = window.localStorage.getItem('token');
      await axios.post(
        `${API}/api/storage-cleanout/${invoiceId}/request-clearance`,
        { notes: '' },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      toast.success(t('cleanouts.requestedSuccess', 'Clearance requested. Awaiting admin verification.'));
      await fetchHolds();
    } catch (e) {
      console.error(e);
      toast.error(t('cleanouts.requestedError', 'Failed to request clearance. Please contact support.'));
    } finally {
      setSubmittingId(null);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-12 text-center" data-testid="cleanouts-loading">
        <Loader2 className="h-8 w-8 animate-spin mx-auto" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl" data-testid="my-cleanouts-page">
      <h1 className="text-2xl sm:text-3xl font-bold mb-2">
        {t('cleanouts.heading', 'My Storage Cleanouts')}
      </h1>
      <p className="text-sm text-muted-foreground mb-6">
        {t('cleanouts.subheading', 'Track the cleanout deadline for every storage locker you have won. Your security deposit is released after admin verification.')}
      </p>

      {holds.length === 0 && (
        <div className="text-center py-16 border rounded-lg" data-testid="cleanouts-empty">
          <p className="text-muted-foreground">
            {t('cleanouts.empty', 'No active cleanout holds. Won storage auctions will appear here.')}
          </p>
        </div>
      )}

      <div className="space-y-4">
        {holds.map((h) => {
          const c = h.cleanout || {};
          const isRequested = c.status === 'pending_verification';
          const isResolved = ['released', 'forfeited', 'captured'].includes(c.status);
          return (
            <Card key={h.invoice_id} className="overflow-hidden" data-testid={`cleanout-card-${h.invoice_id}`}>
              <CardHeader>
                <CardTitle className="text-base sm:text-lg break-words">
                  {h.listing_title || h.facility_name || 'Storage Unit'}
                </CardTitle>
                {h.facility_name && (
                  <p className="text-xs text-muted-foreground">{h.facility_name}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                <CleanoutCountdownTicker deadlineAt={c.deadline_at} status={c.status} />

                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">{t('cleanouts.depositHeld', 'Deposit Held')}</div>
                    <div className="font-semibold">${Number(c.amount_cad || 0).toFixed(2)} CAD</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">{t('cleanouts.windowHours', 'Cleanout Window')}</div>
                    <div className="font-semibold">{c.cleanout_deadline_hours || 72}h</div>
                  </div>
                </div>

                {!isResolved && !isRequested && (
                  <Button
                    onClick={() => handleMarkCleared(h.invoice_id)}
                    disabled={submittingId === h.invoice_id}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                    data-testid={`mark-cleared-btn-${h.invoice_id}`}
                  >
                    {submittingId === h.invoice_id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <>🧼 {t('cleanouts.markCleared', 'Mark Unit as Completely Cleared')}</>
                    )}
                  </Button>
                )}
                {isRequested && (
                  <div className="rounded-md bg-amber-50 border border-amber-300 px-3 py-2 text-xs text-amber-900" data-testid={`cleanout-pending-${h.invoice_id}`}>
                    ⏳ {t('cleanouts.pendingAdminVerification', 'Clearance requested. Awaiting admin verification before deposit is released.')}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
