import React from 'react';
import { Lock, Unlock, DollarSign, CreditCard, Loader2 } from 'lucide-react';

/**
 * VehicleFeeBreakdown — Bilingual display of platform fee calculation.
 * Shows: Platform Fee + Processing Fee = Total Charge
 *
 * Props:
 *   hammerPrice  — the winning bid amount
 *   feeData      — { platform_fee, processing_fee, total_charge_to_buyer } from API
 *   loading      — show skeleton
 */
export const VehicleFeeBreakdown = ({ hammerPrice, feeData, loading = false }) => {
  if (loading) {
    return (
      <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 animate-pulse" data-testid="fee-breakdown-loading">
        <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-3/4 mb-2" />
        <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-1/2" />
      </div>
    );
  }

  if (!feeData) return null;

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-3 bg-slate-50/50 dark:bg-slate-800/30" data-testid="vehicle-fee-breakdown">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        <DollarSign className="w-4 h-4 text-blue-600" />
        <span>Fee Breakdown / Détail des frais</span>
      </div>

      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between text-slate-600 dark:text-slate-400">
          <span>Hammer Price / Prix d'adjudication</span>
          <span className="font-medium">${hammerPrice?.toLocaleString('en-CA', { minimumFractionDigits: 2 })} CAD</span>
        </div>
        <hr className="border-slate-200 dark:border-slate-700" />
        <div className="flex justify-between text-slate-600 dark:text-slate-400">
          <span>Platform Fee (2.5%) / Frais de plateforme (2,5 %)</span>
          <span className="font-medium">${feeData.platform_fee?.toFixed(2)} CAD</span>
        </div>
        <div className="flex justify-between text-slate-600 dark:text-slate-400">
          <span>Processing / Traitement</span>
          <span className="font-medium">${feeData.processing_fee?.toFixed(2)} CAD</span>
        </div>
        <hr className="border-slate-200 dark:border-slate-700" />
        <div className="flex justify-between font-semibold text-slate-800 dark:text-slate-100">
          <span>Total Charge / Frais total</span>
          <span>${feeData.total_charge_to_buyer?.toFixed(2)} CAD</span>
        </div>
      </div>

      <p className="text-[10px] text-slate-500 dark:text-slate-500 leading-relaxed">
        EN: BidVex only collects facilitation and processing fees. The vehicle purchase price is settled directly between buyer and seller.
      </p>
      <hr className="border-slate-100 dark:border-slate-800" />
      <p className="text-[10px] text-slate-500 dark:text-slate-500 leading-relaxed">
        FR: BidVex ne perçoit que les frais de facilitation et de traitement. Le prix d'achat du véhicule est réglé directement entre l'acheteur et le vendeur.
      </p>
    </div>
  );
};


/**
 * SellerContactGate — Shows lock/unlock state for seller contact info.
 * Used on won auction detail pages.
 */
export const SellerContactGate = ({ settlementStatus, sellerData, loading = false }) => {
  if (loading) {
    return (
      <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 flex items-center gap-3" data-testid="seller-contact-loading">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        <span className="text-sm text-slate-500">Loading settlement status...</span>
      </div>
    );
  }

  if (settlementStatus === 'FEE_PAID' && sellerData) {
    return (
      <div className="border-2 border-green-300 bg-green-50 dark:bg-green-900/20 rounded-lg p-4 space-y-2" data-testid="seller-contact-revealed">
        <div className="flex items-center gap-2 text-green-700 dark:text-green-300 font-semibold text-sm">
          <Unlock className="w-4 h-4" />
          Seller Contact Revealed / Coordonnées du vendeur révélées
        </div>
        <div className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
          <p><strong>Name / Nom:</strong> {sellerData.name}</p>
          <p><strong>Email / Courriel:</strong> <a href={`mailto:${sellerData.email}`} className="text-blue-600 hover:underline">{sellerData.email}</a></p>
          {sellerData.phone && <p><strong>Phone / Téléphone:</strong> {sellerData.phone}</p>}
          {sellerData.address && <p><strong>Address / Adresse:</strong> {sellerData.address}</p>}
        </div>
        <p className="text-[10px] text-green-600 dark:text-green-400 mt-2">
          Contact the seller directly to arrange payment and pickup. / Contactez le vendeur directement pour organiser le paiement et la récupération.
        </p>
      </div>
    );
  }

  // Locked state
  return (
    <div className="border-2 border-amber-300 bg-amber-50 dark:bg-amber-900/20 rounded-lg p-4 space-y-2" data-testid="seller-contact-locked">
      <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300 font-semibold text-sm">
        <Lock className="w-4 h-4" />
        {settlementStatus === 'FEE_PROCESSING'
          ? 'Payment Processing... / Paiement en cours...'
          : 'Fee Payment Required / Paiement des frais requis'}
      </div>
      <p className="text-xs text-amber-600 dark:text-amber-400">
        EN: Seller contact information will be revealed once the platform fee payment is confirmed.
      </p>
      <hr className="border-amber-200 dark:border-amber-700" />
      <p className="text-xs text-amber-600 dark:text-amber-400">
        FR: Les coordonnées du vendeur seront révélées une fois le paiement des frais de plateforme confirmé.
      </p>
    </div>
  );
};
