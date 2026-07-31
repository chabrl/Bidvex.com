/**
 * iter442 — Vehicle Listing Choice Modal
 *
 * Shown when a verified dealer clicks any "Create Listing" CTA in the
 * vehicle surface. Two options — single listing or multi-lot auction
 * (up to 500 vehicles) — route to the existing create flows. Neither
 * flow is rebuilt; this modal is purely a router.
 *
 * All copy consumed via `t('vehicleListingChoice.*')` — see
 * `locales/{en,fr}.json`.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Car, LayoutGrid, ArrowRight } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../ui/dialog';

export const VehicleListingChoiceModal = ({ open, onOpenChange }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const go = (path) => {
    onOpenChange?.(false);
    navigate(path);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg"
        data-testid="create-choice-modal"
      >
        <DialogHeader>
          <DialogTitle className="text-xl sm:text-2xl font-bold">
            {t('vehicleListingChoice.title', 'What would you like to create?')}
          </DialogTitle>
          <DialogDescription className="text-sm text-slate-600">
            {t(
              'vehicleListingChoice.subtitle',
              'Choose how you want to list your vehicles. You can switch anytime — nothing is locked in.'
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 pt-2">
          {/* Single Listing */}
          <button
            type="button"
            onClick={() => go('/vehicle-auctions/create')}
            className="group flex items-start gap-4 rounded-xl border-2 border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/50 p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500"
            data-testid="create-choice-single"
          >
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
              <Car className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold text-slate-900 text-base">
                  {t('vehicleListingChoice.single.title', 'Single Listing')}
                </h3>
                <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all" />
              </div>
              <p className="text-xs text-slate-600 mt-1">
                {t(
                  'vehicleListingChoice.single.description',
                  'List one vehicle at a time with full details, photos and reserve pricing.'
                )}
              </p>
            </div>
          </button>

          {/* Multi-Lot Auction */}
          <button
            type="button"
            onClick={() => go('/vehicle-multi-lot/create')}
            className="group flex items-start gap-4 rounded-xl border-2 border-slate-200 hover:border-cyan-500 hover:bg-cyan-50/50 p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500"
            data-testid="create-choice-multi"
          >
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700 group-hover:bg-cyan-600 group-hover:text-white transition-colors">
              <LayoutGrid className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold text-slate-900 text-base">
                  {t(
                    'vehicleListingChoice.multi.title',
                    'Multi-Lot Auction (up to 500 vehicles)'
                  )}
                </h3>
                <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-cyan-600 group-hover:translate-x-0.5 transition-all" />
              </div>
              <p className="text-xs text-slate-600 mt-1">
                {t(
                  'vehicleListingChoice.multi.description',
                  'Run one event with multiple lots — perfect for fleet sales, dealer clearances and consignment auctions.'
                )}
              </p>
            </div>
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default VehicleListingChoiceModal;
