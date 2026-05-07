import API_BASE from '../../config';
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2, DollarSign, ExternalLink } from 'lucide-react';
import StorageFooterBanner from './StorageFooterBanner';

const API = API_BASE;

const STATUS_EN = {
  held: 'Authorized 🔒', authorized: 'Authorized 🔒',
  applied: 'Applied ✅', refunded: 'Refunded ✔️', forfeited: 'Forfeited ❌',
};
const STATUS_FR = {
  held: 'Autorisé 🔒', authorized: 'Autorisé 🔒',
  applied: 'Appliqué ✅', refunded: 'Remboursé ✔️', forfeited: 'Confisqué ❌',
};
const STATUS_COLOR = {
  held: 'bg-amber-100 text-amber-800',
  authorized: 'bg-amber-100 text-amber-800',
  applied: 'bg-emerald-100 text-emerald-800',
  refunded: 'bg-blue-100 text-blue-800',
  forfeited: 'bg-red-100 text-red-800',
};

/**
 * My Storage Deposits — iter172.
 * Always bilingual EN + FR (Bill 96).
 */
const MyStorageDeposits = () => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState({ total: 0, deposits: [] });
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API}/my-storage-deposits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data || { total: 0, deposits: [] });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 p-4">
        <Card className="max-w-md p-8 text-center">
          <p className="mb-1">Please sign in to view your deposits.</p>
          <p className="italic text-sm text-muted-foreground mb-4">Connectez-vous pour voir vos dépôts.</p>
          <Button onClick={() => navigate('/auth')}>{t('storage.myDeposits.signIn')}</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="my-deposits-page">
      <div className="max-w-5xl mx-auto px-4">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <DollarSign className="h-7 w-7 text-emerald-500" />
          {t('storage.myDeposits.title')}
        </h1>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              {t('storage.myDeposits.title')}
              <Badge variant="outline" className="ml-2">{data.total}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : data.deposits.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                {t('storage.myDeposits.noActiveDeposits')}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="my-deposits-table">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="pb-2 pr-3">{t('storage.myDeposits.facility')}</th>
                      <th className="pb-2 pr-3 text-right">{t('storage.myDeposits.amount')}</th>
                      <th className="pb-2 pr-3">{t('storage.myDeposits.status')}</th>
                      <th className="pb-2 pr-3">{t('storage.myDeposits.date')}</th>
                      <th className="pb-2 pr-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.deposits.map((d, i) => (
                      <tr key={d.auction_id + ':' + i} className="border-b hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 pr-3">
                          <div className="font-medium">#{d.auction_unit_number}</div>
                          <div className="text-xs text-muted-foreground">
                            {d.facility_name} • {d.facility_city}, {d.facility_province}
                          </div>
                        </td>
                        <td className="py-3 pr-3 text-right font-semibold">${Number(d.amount).toFixed(2)} CAD</td>
                        <td className="py-3 pr-3">
                          <Badge className={STATUS_COLOR[d.status] || ''}>
                            {(isFr ? STATUS_FR : STATUS_EN)[d.status] || d.status}
                          </Badge>
                        </td>
                        <td className="py-3 pr-3 text-xs text-muted-foreground">
                          {d.created_at ? new Date(d.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td className="py-3 pr-3">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/storage-auctions/${d.auction_id}`)}
                            data-testid={`my-deposit-view-${d.auction_id}`}
                          >
                            <ExternalLink className="h-3.5 w-3.5 mr-1" />
                            View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export default MyStorageDeposits;
