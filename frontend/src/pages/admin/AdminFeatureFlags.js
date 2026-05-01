/**
 * AdminFeatureFlags — iter176
 * =============================
 * Admin tab to toggle platform feature flags. Surfaces:
 *   • Vehicle Auctions on/off (with waitlist signup count)
 *
 * Endpoints:
 *   GET   /api/admin/feature-flags
 *   PATCH /api/admin/feature-flags/{key}        body { enabled }
 *   GET   /api/admin/waitlist/vehicle-auctions/count
 *
 * Bilingual EN+FR (Bill 96) on every label.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Switch } from '../../components/ui/switch';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Car, Flag, Users, RefreshCw } from 'lucide-react';
import { invalidateFeatureFlag } from '../../hooks/useFeatureFlag';

const API = API_BASE;

const FLAG_META = {
  vehicle_auctions_enabled: {
    title_en: 'Vehicle Auctions',
    title_fr: 'Enchères de véhicules',
    Icon: Car,
  },
};

const AdminFeatureFlags = () => {
  const { token } = useAuth();
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState({});
  const [vehicleWaitlistCount, setVehicleWaitlistCount] = useState(null);

  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const fetchFlags = useCallback(async () => {
    setLoading(true);
    try {
      const [flagsRes, countRes] = await Promise.all([
        axios.get(`${API}/admin/feature-flags`, auth),
        axios.get(`${API}/admin/waitlist/vehicle-auctions/count`, auth).catch(() => ({ data: { count: 0 } })),
      ]);
      setFlags(flagsRes.data?.flags || []);
      setVehicleWaitlistCount(countRes.data?.count ?? 0);
    } catch (e) {
      toast.error('Failed to load feature flags · Échec du chargement');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchFlags(); }, [fetchFlags]);

  const handleToggle = async (flag, nextEnabled) => {
    const key = flag.key;
    const original = flag.enabled;
    // optimistic UI
    setFlags((cur) => cur.map((f) => (f.key === key ? { ...f, enabled: nextEnabled } : f)));
    setUpdating((u) => ({ ...u, [key]: true }));
    try {
      const r = await axios.patch(`${API}/admin/feature-flags/${key}`, { enabled: nextEnabled }, auth);
      setFlags((cur) => cur.map((f) => (f.key === key ? { ...f, ...r.data } : f)));
      invalidateFeatureFlag(key);
      toast.success(
        key === 'vehicle_auctions_enabled'
          ? 'Vehicle auctions page updated. · Page d\'enchères mise à jour.'
          : 'Feature flag updated. · Indicateur mis à jour.'
      );
    } catch (e) {
      // revert on error
      setFlags((cur) => cur.map((f) => (f.key === key ? { ...f, enabled: original } : f)));
      toast.error('Update failed · Mise à jour échouée');
    } finally {
      setUpdating((u) => { const n = { ...u }; delete n[key]; return n; });
    }
  };

  return (
    <div data-testid="admin-feature-flags">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Flag className="h-6 w-6 text-blue-600" />
            Feature Flags · Indicateurs de fonctionnalité
          </h2>
          <p className="text-sm text-muted-foreground">
            Toggle platform features on or off · Activer ou désactiver les fonctionnalités
          </p>
        </div>
        <button
          onClick={fetchFlags}
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          data-testid="admin-feature-flags-refresh"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh · Rafraîchir
        </button>
      </div>

      {loading ? (
        <div className="py-12 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
      ) : flags.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No feature flags · Aucun indicateur</p>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {flags.map((flag) => {
            const meta = FLAG_META[flag.key] || { title_en: flag.key, title_fr: flag.key, Icon: Flag };
            const Icon = meta.Icon;
            const isUpdating = !!updating[flag.key];
            return (
              <Card
                key={flag.key}
                className="rounded-2xl border-slate-200 dark:border-slate-700"
                data-testid={`flag-card-${flag.key}`}
              >
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-2 text-lg">
                      <Icon className="h-5 w-5 text-blue-600" />
                      {meta.title_en} · {meta.title_fr}
                    </span>
                    <span className="flex items-center gap-2">
                      {flag.enabled ? (
                        <Badge className="bg-emerald-500 text-white" data-testid={`flag-status-${flag.key}-active`}>
                          ● Active · Actif
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground" data-testid={`flag-status-${flag.key}-coming-soon`}>
                          ◌ Coming Soon mode · Mode Bientôt
                        </Badge>
                      )}
                      {isUpdating ? (
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      ) : (
                        <Switch
                          checked={flag.enabled}
                          onCheckedChange={(checked) => handleToggle(flag, checked)}
                          data-testid={`flag-toggle-${flag.key}`}
                        />
                      )}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0 text-sm text-muted-foreground space-y-2">
                  <p>{flag.description_en}</p>
                  <p className="italic">{flag.description_fr}</p>

                  {flag.key === 'vehicle_auctions_enabled' && vehicleWaitlistCount !== null && (
                    <div
                      className="mt-3 inline-flex items-center gap-2 rounded-md border border-cyan-200 bg-cyan-50 dark:bg-cyan-950/30 dark:border-cyan-900 px-3 py-1.5"
                      data-testid="vehicle-waitlist-count"
                    >
                      <Users className="h-3.5 w-3.5 text-cyan-700 dark:text-cyan-300" />
                      <span className="text-xs font-semibold text-cyan-900 dark:text-cyan-100">
                        Waitlist signups · Inscriptions : <strong>{vehicleWaitlistCount}</strong>
                      </span>
                    </div>
                  )}

                  {flag.updated_at && (
                    <p className="text-[11px] text-muted-foreground/70">
                      Last updated · Dernière modif. : {new Date(flag.updated_at).toLocaleString()} {flag.updated_by ? `· ${flag.updated_by}` : ''}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AdminFeatureFlags;
