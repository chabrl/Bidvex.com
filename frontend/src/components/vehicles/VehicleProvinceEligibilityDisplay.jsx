/**
 * iter285 — Vehicle Province Eligibility Display (Bug 4 — buyer side).
 *
 * Renders the province-registration eligibility badges on the vehicle
 * detail page so buyers can immediately see whether they can register
 * the vehicle in their home province.
 *
 * Three render cases (per spec):
 *   1. eligible_provinces === ['ALL'] (or all 13)  → "Eligible everywhere".
 *   2. specific provinces                         → row of green ✅ / red ❌ pills.
 *   3. empty / missing                            → "Eligibility TBD" warning.
 *
 * If `buyerProvince` is provided (logged-in user profile), a top "Based on
 * your location" badge is shown to call out whether THIS buyer can register.
 */
import React from 'react';
import { CA_PROVINCES } from '../../components/vehicles/VehicleProvinceEligibility';

const INSPECTION_LABEL = {
  safety_certified: 'Safety Certified',
  e_tested:         'e-Tested',
  mvi_passed:       'MVI Passed',
  as_is:            'As-Is / No Cert.',
};

const VehicleProvinceEligibilityDisplay = ({
  listing,
  buyerProvince,
  isFr = false,
}) => {
  const raw = listing?.eligible_provinces;
  const inspection = listing?.inspection_status;

  // Case 3 — not specified.
  if (!Array.isArray(raw) || raw.length === 0) {
    return (
      <div
        data-testid="vehicle-province-eligibility-tbd"
        className="rounded-lg border p-3 text-xs"
        style={{ background: '#fffbeb', borderColor: '#f6c90e' }}
      >
        <p className="font-semibold text-amber-900 mb-1">
          ⚠️ {isFr ? "Éligibilité provinciale non spécifiée" : "Province eligibility not specified"}
        </p>
        <p className="text-amber-800">
          {isFr
            ? "Contactez le vendeur pour les informations d'immatriculation."
            : "Contact seller for registration information."}
        </p>
      </div>
    );
  }

  const allCodes = CA_PROVINCES.map(p => p.code);
  const isAll = raw.length === 1 && raw[0] === 'ALL';
  const eligibleSet = new Set(isAll ? allCodes : raw);
  const everywhere = isAll || eligibleSet.size === allCodes.length;

  const buyerCode = (buyerProvince || '').toUpperCase();
  const buyerEligible = buyerCode && eligibleSet.has(buyerCode);

  return (
    <div
      data-testid="vehicle-province-eligibility-display"
      className="rounded-lg border p-3 text-xs space-y-2"
      style={{ background: everywhere ? '#f0fff4' : '#ffffff', borderColor: everywhere ? '#c6f6d5' : '#e2e8f0' }}
    >
      {/* Buyer-province callout (only when we know the buyer's province) */}
      {buyerCode && (
        <div
          data-testid="vehicle-province-eligibility-buyer-badge"
          className="text-xs font-semibold p-2 rounded"
          style={{
            background: buyerEligible ? '#f0fff4' : '#fff5f5',
            color:      buyerEligible ? '#276749' : '#e53e3e',
            border:     `1px solid ${buyerEligible ? '#c6f6d5' : '#feb2b2'}`,
          }}
        >
          {isFr
            ? `Selon votre emplacement (${buyerCode}): ${buyerEligible ? '✅ Admissible à l\u2019immatriculation' : '❌ Non admissible — contactez le vendeur'}`
            : `Based on your location (${buyerCode}): ${buyerEligible ? '✅ Eligible to register' : '❌ Not eligible — contact seller'}`}
        </div>
      )}

      {everywhere ? (
        <p className="font-semibold" style={{ color: '#276749' }}>
          ✅ {isFr
            ? "Admissible à l'immatriculation dans toutes les provinces canadiennes"
            : "Eligible for registration in all Canadian provinces"}
        </p>
      ) : (
        <>
          <p className="font-semibold text-slate-800">
            {isFr ? "Admissibilité provinciale" : "Province Eligibility"}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {CA_PROVINCES.map(({ code }) => {
              const ok = eligibleSet.has(code);
              return (
                <span
                  key={code}
                  data-testid={`vehicle-province-pill-${code.toLowerCase()}`}
                  className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded font-mono font-semibold"
                  style={{
                    background: ok ? '#f0fff4' : '#fff5f5',
                    color:      ok ? '#276749' : '#e53e3e',
                    border:     `1px solid ${ok ? '#c6f6d5' : '#feb2b2'}`,
                    fontSize:   '10px',
                  }}
                >
                  {ok ? '✅' : '❌'} {code}
                </span>
              );
            })}
          </div>
        </>
      )}

      {inspection && inspection !== 'as_is' && (
        <p className="text-[11px] text-slate-700">
          <span className="font-semibold">{isFr ? "Inspection" : "Inspection"}: </span>
          {INSPECTION_LABEL[inspection] || inspection} ✅
        </p>
      )}
      {inspection === 'as_is' && (
        <p className="text-[11px] text-slate-600 italic">
          {isFr ? "Inspection : Tel quel (aucune certification)" : "Inspection: As-Is / No Certification"}
        </p>
      )}
    </div>
  );
};

export default VehicleProvinceEligibilityDisplay;
