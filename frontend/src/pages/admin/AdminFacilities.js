/**
 * AdminFacilities — iter178 (FIX 6)
 * ===================================
 * Lists all registered storage facilities with Verify/Suspend/Delete actions.
 * Reuses existing /api/admin/storage-facilities backend endpoints.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { Loader2, Building2, ShieldCheck, Ban, Trash2 } from 'lucide-react';

const API = API_BASE;

const STATUS_STYLES = {
  pending:  'bg-amber-100 text-amber-800',
  verified: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
  suspended:'bg-slate-200 text-slate-700',
};

const AdminFacilities = () => {
  const { token } = useAuth();
  const [facilities, setFacilities] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const loadFacilities = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/storage-facilities`, { headers: { Authorization: `Bearer ${token}` } });
      setFacilities(r.data?.facilities || r.data || []);
    } catch (e) {
      toast.error('Failed to load facilities · Échec');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadFacilities(); }, [loadFacilities]);

  const act = async (facility, action) => {
    if (action === 'delete' && !window.confirm('Delete this facility? · Supprimer cette facilité ?')) return;
    try {
      const endpoints = {
        verify: `/admin/storage-facilities/${facility.id}/verify`,
        suspend: `/admin/storage-facilities/${facility.id}/suspend`,
        delete: `/admin/storage-facilities/${facility.id}`,
      };
      if (action === 'delete') {
        await axios.delete(`${API}${endpoints.delete}`, auth);
      } else {
        await axios.post(`${API}${endpoints[action]}`, {}, auth);
      }
      toast.success(`Facility ${action}d · ${action}`);
      loadFacilities();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${action} failed`);
    }
  };

  const filtered = facilities.filter((f) =>
    !filter || (f.company_name || '').toLowerCase().includes(filter.toLowerCase()) ||
               (f.city || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div data-testid="admin-facilities">
      <Card className="rounded-2xl">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-blue-600" />
              Storage Facilities · Facilités d'entreposage
            </CardTitle>
            <p className="text-sm text-muted-foreground">Verify, suspend or delete facility operators</p>
          </div>
          <Input
            placeholder="Search · Rechercher"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="max-w-xs"
            data-testid="admin-facilities-filter"
          />
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-10 flex justify-center"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>
          ) : filtered.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No facilities · Aucune facilité</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground border-b">
                  <tr>
                    <th className="text-left p-2">Company · Entreprise</th>
                    <th className="text-left p-2">City · Ville</th>
                    <th className="text-left p-2">Contact</th>
                    <th className="text-left p-2">Status · Statut</th>
                    <th className="text-right p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => (
                    <tr key={f.id} className="border-b hover:bg-slate-50" data-testid={`admin-facility-row-${f.id}`}>
                      <td className="p-2 font-semibold">{f.company_name || '—'}</td>
                      <td className="p-2 text-xs">{f.city}, {f.province}</td>
                      <td className="p-2 text-xs">{f.email}<br/><span className="text-muted-foreground">{f.phone || ''}</span></td>
                      <td className="p-2">
                        <Badge className={STATUS_STYLES[f.status] || 'bg-slate-100'}>{f.status || 'unverified'}</Badge>
                      </td>
                      <td className="p-2 text-right space-x-1">
                        {f.status !== 'verified' && (
                          <Button size="sm" variant="outline" onClick={() => act(f, 'verify')} className="border-emerald-300 text-emerald-700" data-testid={`facility-verify-${f.id}`}>
                            <ShieldCheck className="h-3 w-3 mr-1" />Verify · Vérifier
                          </Button>
                        )}
                        {f.status !== 'suspended' && (
                          <Button size="sm" variant="outline" onClick={() => act(f, 'suspend')} className="border-amber-300 text-amber-700" data-testid={`facility-suspend-${f.id}`}>
                            <Ban className="h-3 w-3 mr-1" />Suspend · Suspendre
                          </Button>
                        )}
                        <Button size="sm" variant="outline" onClick={() => act(f, 'delete')} className="border-red-300 text-red-700" data-testid={`facility-delete-${f.id}`}>
                          <Trash2 className="h-3 w-3 mr-1" />Delete · Supprimer
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
  );
};

export default AdminFacilities;
