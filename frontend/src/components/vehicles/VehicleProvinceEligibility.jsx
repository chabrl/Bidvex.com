/**
 * iter285 — Vehicle Province Eligibility Picker (Bug 4).
 *
 * Canadian-province multi-select with a "Select All" master toggle and an
 * inspection-status radio. Used in the vehicle listing wizard (Step 2 —
 * Specifications) so sellers explicitly state which provinces a buyer can
 * register the vehicle in. This is a compliance requirement, not cosmetic.
 *
 * Value shape returned via `onChange`:
 *   {
 *     eligible_provinces: ["ALL"] | ["QC","ON",...],
 *     inspection_status:  "safety_certified" | "e_tested" | "as_is" | "mvi_passed",
 *   }
 *
 * Display rules:
 *   - "Select All" → eligible_provinces === ["ALL"] (single sentinel).
 *   - Unchecking any individual auto-flips back to an explicit list.
 *   - Selecting all 13 individually collapses back to ["ALL"].
 */
import React, { useMemo } from 'react';
import { Checkbox } from '../../components/ui/checkbox';
import { Label } from '../../components/ui/label';

export const CA_PROVINCES = [
  { code: 'QC', label: 'Quebec / Québec' },
  { code: 'ON', label: 'Ontario' },
  { code: 'BC', label: 'British Columbia / Colombie-Britannique' },
  { code: 'AB', label: 'Alberta' },
  { code: 'MB', label: 'Manitoba' },
  { code: 'SK', label: 'Saskatchewan' },
  { code: 'NS', label: 'Nova Scotia / Nouvelle-Écosse' },
  { code: 'NB', label: 'New Brunswick / Nouveau-Brunswick' },
  { code: 'PE', label: 'Prince Edward Island / Île-du-Prince-Édouard' },
  { code: 'NL', label: 'Newfoundland & Labrador / Terre-Neuve-et-Labrador' },
  { code: 'NT', label: 'Northwest Territories / Territoires du Nord-Ouest' },
  { code: 'YT', label: 'Yukon' },
  { code: 'NU', label: 'Nunavut' },
];

const INSPECTION_OPTIONS = [
  { value: 'safety_certified', label: 'Safety Certified' },
  { value: 'e_tested',         label: 'e-Tested (Ontario)' },
  { value: 'mvi_passed',       label: 'MVI Passed (Atlantic)' },
  { value: 'as_is',            label: 'As-Is / No Certification' },
];

const VehicleProvinceEligibility = ({ value = ['ALL'], inspectionStatus = 'as_is', onChange }) => {
  const allCodes = useMemo(() => CA_PROVINCES.map(p => p.code), []);
  const isAll = Array.isArray(value) && value.length === 1 && value[0] === 'ALL';
  const selected = isAll ? new Set(allCodes) : new Set(value || []);

  const emit = (provinces, inspection) => {
    const explicit = Array.from(provinces);
    const collapsed = explicit.length === allCodes.length ? ['ALL'] : explicit;
    onChange?.({ eligible_provinces: collapsed, inspection_status: inspection });
  };

  const toggleAll = (checked) => {
    emit(checked ? new Set(allCodes) : new Set(), inspectionStatus);
  };

  const toggleOne = (code, checked) => {
    const next = new Set(selected);
    if (checked) next.add(code);
    else next.delete(code);
    emit(next, inspectionStatus);
  };

  return (
    <div
      data-testid="vehicle-province-eligibility"
      className="space-y-4 p-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/30"
    >
      <div>
        <Label className="text-sm font-semibold">
          Province Registration Eligibility / Admissibilité provinciale
        </Label>
        <p className="text-[11px] text-muted-foreground mt-1">
          In which provinces can this vehicle be registered? Buyers in
          non-eligible provinces will see a warning.
        </p>
      </div>

      <label className="flex items-center gap-2 pb-2 border-b border-slate-200 dark:border-slate-700">
        <Checkbox
          checked={isAll}
          onCheckedChange={(c) => toggleAll(c === true)}
          data-testid="vehicle-province-all"
        />
        <span className="text-sm font-semibold">All Provinces / Toutes les provinces</span>
      </label>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {CA_PROVINCES.map(({ code, label }) => (
          <label
            key={code}
            className="flex items-center gap-2 text-sm cursor-pointer"
            data-testid={`vehicle-province-${code.toLowerCase()}-row`}
          >
            <Checkbox
              checked={selected.has(code)}
              onCheckedChange={(c) => toggleOne(code, c === true)}
              data-testid={`vehicle-province-${code.toLowerCase()}-checkbox`}
            />
            <span><span className="font-mono font-semibold">{code}</span> — {label.split(' / ')[0]}</span>
          </label>
        ))}
      </div>

      <div className="pt-3 border-t border-slate-200 dark:border-slate-700">
        <Label className="text-sm font-semibold">
          Inspection / Certification Status
        </Label>
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {INSPECTION_OPTIONS.map(({ value: v, label }) => (
            <label
              key={v}
              className="flex items-center gap-2 text-sm cursor-pointer"
              data-testid={`vehicle-inspection-${v}-row`}
            >
              <input
                type="radio"
                name="vehicle-inspection-status"
                value={v}
                checked={inspectionStatus === v}
                onChange={() => emit(selected, v)}
                data-testid={`vehicle-inspection-${v}-radio`}
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
};

export default VehicleProvinceEligibility;
