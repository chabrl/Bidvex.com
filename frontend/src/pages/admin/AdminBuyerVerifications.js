/**
 * iter201 — Phase 3 / 3B sub-tab 3 — Admin Buyer Verifications.
 *
 * Lists pending buyer-verification submissions from restricted-province
 * buyers (ON/NB/NS/PE/NL). Admin can approve or reject with a reason; the
 * backend fires a bilingual email on either path.
 */
import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Check, X, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';

const API = API_BASE;

const AdminBuyerVerifications = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);
  const [reasonByUser, setReasonByUser] = useState({});

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const r = await axios.get(`${API}/admin/buyer-verifications/pending`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load buyer verifications');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleDecision = async (userId, decision) => {
    if (decision === 'reject') {
      const reason = (reasonByUser[userId] || '').trim();
      if (!reason) {
        toast.error('Please enter a rejection reason');
        return;
      }
    }
    setActing(`${userId}-${decision}`);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/admin/buyer-verifications/${userId}/decision`,
        { decision, rejection_reason: reasonByUser[userId] || null },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(decision === 'approve' ? 'Approved — buyer notified' : 'Rejected — buyer notified');
      fetchList();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Action failed');
    } finally {
      setActing(null);
    }
  };

  return (
    <Card data-testid="admin-buyer-verifications">
      <CardHeader>
        <CardTitle>Buyer Verification Queue</CardTitle>
        <p className="text-xs text-slate-500">Restricted-province buyers (ON/NB/NS/PE/NL) submit their dealer credentials here for review. Approving sends a bilingual email and unlocks bidding for that province.</p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
        ) : items.length === 0 ? (
          <div className="text-sm text-slate-500 text-center py-8" data-testid="buyer-verifications-empty">No pending buyer verifications.</div>
        ) : (
          <div className="space-y-3">
            {items.map((it) => (
              <div key={it.user_id} className="rounded-lg border p-3" data-testid={`buyer-verif-${it.user_id}`}>
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold">{it.name || it.email}</p>
                    <p className="text-xs text-slate-500">{it.email}</p>
                    <div className="flex flex-wrap gap-2 mt-1.5 text-[11px]">
                      <Badge variant="outline">{it.province}</Badge>
                      <Badge>{it.type === 'dealer_representative' ? 'Dealer Rep' : 'Dealer'}</Badge>
                      <span className="text-slate-500 font-mono">#{it.license_number}</span>
                      {it.dealer_business_name && <span className="text-slate-500">{it.dealer_business_name}</span>}
                    </div>
                    {it.document_path && (
                      <a
                        href={`${API}/uploads/${it.document_path}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1.5 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 underline-offset-2 hover:underline"
                      >
                        <FileText className="h-3 w-3" /> View document
                      </a>
                    )}
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Input
                    placeholder="Rejection reason (required for reject)"
                    value={reasonByUser[it.user_id] || ''}
                    onChange={(e) => setReasonByUser((p) => ({ ...p, [it.user_id]: e.target.value }))}
                    className="text-sm h-8"
                    data-testid={`buyer-verif-reason-${it.user_id}`}
                  />
                  <Button
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    disabled={acting === `${it.user_id}-approve`}
                    onClick={() => handleDecision(it.user_id, 'approve')}
                    data-testid={`buyer-verif-approve-${it.user_id}`}
                  >
                    <Check className="h-4 w-4 mr-1" /> Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={acting === `${it.user_id}-reject`}
                    onClick={() => handleDecision(it.user_id, 'reject')}
                    data-testid={`buyer-verif-reject-${it.user_id}`}
                  >
                    <X className="h-4 w-4 mr-1" /> Reject
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AdminBuyerVerifications;
