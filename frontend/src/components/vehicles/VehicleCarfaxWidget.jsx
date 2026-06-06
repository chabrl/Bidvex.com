/**
 * iter286 — Vehicle Carfax Documents widget (Bug 5).
 *
 * Renders three render states based on the authenticated user:
 *   • Authenticated + broker partner → "View Carfax Report" CTA
 *   • Authenticated + individual buyer → locked-state teaser with
 *     "Become a Broker Partner" CTA
 *   • Unauthenticated → "Sign in to view documents" CTA
 *
 * The actual document URL is fetched lazily from
 * GET /api/vehicle-auctions/{id}/carfax (broker-gated). The widget
 * never renders the URL inline — it opens in a new tab on click so
 * the buyer's bidding session is preserved.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../../config';
import { Lock, FileText, ExternalLink, AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';

export default function VehicleCarfaxWidget({ vehicleId, user, isFr = false }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const isAuthenticated = !!user;
  const isBroker = !!(
    user?.is_broker_partner ||
    user?.is_broker ||
    user?.broker_partner_status === 'active' ||
    user?.broker_partner_status === 'approved' ||
    user?.role === 'admin'
  );

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const handleViewReport = async () => {
    setError('');
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/vehicle-auctions/${vehicleId}/carfax`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      const url = r.data?.carfax_url || r.data?.carfax_file;
      if (!url) {
        setError(isFr
          ? "Aucun rapport Carfax n\u2019est disponible pour ce v\u00e9hicule."
          : 'No Carfax report is available for this vehicle.');
        return;
      }
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      const code = e?.response?.data?.detail?.code;
      if (code === 'broker_required') {
        setError(isFr
          ? "Acc\u00e8s aux Carfax r\u00e9serv\u00e9 aux partenaires courtiers v\u00e9rifi\u00e9s."
          : 'Carfax reports are only available to verified broker partners.');
      } else {
        setError(isFr ? "Erreur lors du chargement du rapport." : 'Failed to load the report.');
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Render Case 3 — Not authenticated ───────────────────────────────
  if (!isAuthenticated) {
    return (
      <div
        data-testid="vehicle-carfax-signin"
        className="rounded-lg border p-3 text-xs flex items-center justify-between gap-3"
        style={{ background: '#f7fafc', borderColor: '#cbd5e0' }}
      >
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-slate-600" />
          <span className="text-slate-700">
            {isFr ? "Connectez-vous pour voir les documents du v\u00e9hicule" : 'Sign in to view vehicle documents'}
          </span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigate('/auth')}
          data-testid="vehicle-carfax-signin-btn"
        >
          {isFr ? "Se connecter" : "Sign In"} →
        </Button>
      </div>
    );
  }

  // ── Render Case 1 — Broker partner ─────────────────────────────────
  if (isBroker) {
    return (
      <div
        data-testid="vehicle-carfax-broker"
        className="rounded-lg border p-3 text-xs space-y-2"
        style={{ background: '#f0fff4', borderColor: '#c6f6d5' }}
      >
        <p className="font-semibold flex items-center gap-1.5" style={{ color: '#276749' }}>
          <FileText className="h-4 w-4" />
          {isFr ? "Documents du v\u00e9hicule" : "Vehicle Documents"}
        </p>
        <Button
          size="sm"
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          onClick={handleViewReport}
          disabled={loading}
          data-testid="vehicle-carfax-view-btn"
        >
          {loading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <ExternalLink className="h-3 w-3 mr-1" />}
          {isFr ? "Voir le rapport Carfax" : "View Carfax Report"} →
        </Button>
        {error && (
          <p className="text-rose-700 text-[11px] flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> {error}
          </p>
        )}
      </div>
    );
  }

  // ── Render Case 2 — Individual buyer (locked) ──────────────────────
  return (
    <div
      data-testid="vehicle-carfax-locked"
      className="rounded-lg p-3 text-xs space-y-2"
      style={{ background: '#f7fafc', border: '1px dashed #cbd5e0' }}
    >
      <p className="font-semibold flex items-center gap-1.5 text-slate-700">
        <FileText className="h-4 w-4" />
        {isFr ? "Documents du v\u00e9hicule — acc\u00e8s courtier" : "Vehicle Documents — Broker Access Only"}
      </p>
      <div className="space-y-1 text-slate-500">
        <p className="flex items-center gap-1.5">
          <Lock className="h-3 w-3" /> {isFr ? "Rapport Carfax" : "Carfax Report"}
        </p>
        <p className="flex items-center gap-1.5">
          <Lock className="h-3 w-3" /> {isFr ? "Rapport d\u2019inspection" : "Inspection Report"}
        </p>
      </div>
      <Button
        size="sm"
        variant="outline"
        onClick={() => navigate('/become-a-broker')}
        data-testid="vehicle-carfax-broker-cta"
        className="w-full"
      >
        {isFr ? "Devenir partenaire courtier" : "Become a Broker Partner"} →
      </Button>
    </div>
  );
}
