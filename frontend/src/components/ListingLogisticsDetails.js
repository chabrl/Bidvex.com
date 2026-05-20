import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Truck, MapPin, Calendar, Package2 } from 'lucide-react';

/**
 * FEATURE PATCH v9 / Feature 2
 *
 * Conditionally renders Visit, Shipping & Pickup, and Item Details sections
 * for a public listing page. Hides any field whose value is null / empty /
 * false. Booleans render as "Yes" / "No". Works for single-item listings,
 * lots and vehicles (the caller passes whichever subset is meaningful).
 */

const _isMeaningful = (v) => {
  if (v === null || v === undefined) return false;
  if (typeof v === 'string') return v.trim().length > 0;
  if (typeof v === 'boolean') return true; // boolean false is meaningful (rendered as "No")
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'object') return Object.values(v).some((x) => _isMeaningful(x));
  if (typeof v === 'number') return true;
  return Boolean(v);
};

const _ynBadge = (val, t) => {
  if (val === true) {
    return <Badge className="bg-emerald-100 text-emerald-900 border border-emerald-200">{t('common.yes', 'Yes')}</Badge>;
  }
  if (val === false) {
    return <Badge className="bg-rose-100 text-rose-900 border border-rose-200">{t('common.no', 'No')}</Badge>;
  }
  return null;
};

const Row = ({ label, value, t }) => {
  if (!_isMeaningful(value)) return null;
  let display;
  if (typeof value === 'boolean') {
    display = _ynBadge(value, t);
  } else if (Array.isArray(value)) {
    display = value.filter(_isMeaningful).join(', ');
  } else if (typeof value === 'object') {
    display = (
      <div className="space-y-1">
        {Object.entries(value)
          .filter(([, v]) => _isMeaningful(v))
          .map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 text-xs">
              <span className="text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</span>
              <span className="font-medium text-right">
                {typeof v === 'boolean' ? _ynBadge(v, t) : String(v)}
              </span>
            </div>
          ))}
      </div>
    );
  } else {
    display = String(value);
  }
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-1 sm:gap-3 py-2 border-b border-slate-100 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium sm:max-w-[60%] sm:text-right">{display}</span>
    </div>
  );
};

const ListingLogisticsDetails = ({ listing }) => {
  const { t } = useTranslation();
  if (!listing) return null;

  const shipping = listing.shipping_info || null;
  const visit = listing.visit_availability || null;
  const pickup = listing.pickup_locations || listing.pickup_details || null;
  const itemDetails = listing.item_details || null;

  // Compute whether each subsection has *any* meaningful data
  const hasShipping = _isMeaningful(shipping);
  const hasVisit = _isMeaningful(visit);
  const hasPickup = _isMeaningful(pickup);
  const hasItemDetails = _isMeaningful(itemDetails);
  const hasQuantity = (listing.quantity || 1) > 1 || listing.multiply_hammer_by_quantity;

  if (!hasShipping && !hasVisit && !hasPickup && !hasItemDetails && !hasQuantity) {
    return null;
  }

  return (
    <div className="space-y-4" data-testid="listing-logistics-details">
      {/* Quantity badges — FEATURE PATCH v9 / Feature 4 */}
      {hasQuantity && (
        <Card className="glassmorphism" data-testid="listing-quantity-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Package2 className="h-4 w-4 text-cyan-600" />
              {t('listingDetail.quantityTitle', 'Quantity Information')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            <Row label={t('listingDetail.quantity', 'Quantity')} value={listing.quantity} t={t} />
            <Row
              label={t('listingDetail.multiplyHammer', 'Hammer price applies per unit')}
              value={!!listing.multiply_hammer_by_quantity}
              t={t}
            />
            {listing.multiply_hammer_by_quantity && (listing.quantity || 1) > 1 && (
              <div className="text-xs text-cyan-700 bg-cyan-50 border border-cyan-100 rounded-md px-3 py-2 mt-1">
                {t(
                  'listingDetail.multiplyHammerNotice',
                  'The winning bid (hammer price) will be multiplied by {{qty}} units. All platform/broker fees are calculated on the full base amount.',
                  { qty: listing.quantity }
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {hasItemDetails && (
        <Card className="glassmorphism" data-testid="listing-item-details-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('listingDetail.itemDetails', 'Item Details')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 pt-0">
            {Object.entries(itemDetails)
              .filter(([, v]) => _isMeaningful(v))
              .map(([k, v]) => (
                <Row key={k} label={k.replace(/_/g, ' ')} value={v} t={t} />
              ))}
          </CardContent>
        </Card>
      )}

      {hasShipping && (
        <Card className="glassmorphism" data-testid="listing-shipping-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Truck className="h-4 w-4 text-blue-600" />
              {t('listingDetail.shippingTitle', 'Shipping & Delivery')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 pt-0">
            <Row label={t('listingDetail.shippingAvailable', 'Shipping available')} value={!!shipping.available} t={t} />
            <Row label={t('listingDetail.shippingMethods', 'Methods')} value={shipping.methods} t={t} />
            <Row label={t('listingDetail.shippingRates', 'Rates')} value={shipping.rates} t={t} />
            <Row label={t('listingDetail.deliveryTime', 'Estimated delivery')} value={shipping.delivery_time} t={t} />
            <Row label={t('listingDetail.shippingNotes', 'Notes')} value={shipping.notes} t={t} />
          </CardContent>
        </Card>
      )}

      {hasPickup && (
        <Card className="glassmorphism" data-testid="listing-pickup-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <MapPin className="h-4 w-4 text-amber-600" />
              {t('listingDetail.pickupTitle', 'Pickup Information')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 pt-0">
            {Array.isArray(pickup) ? (
              pickup.map((p, idx) => (
                <div key={idx} className="rounded-md border border-amber-100 bg-amber-50/40 p-2 space-y-1 mb-2">
                  {Object.entries(p)
                    .filter(([, v]) => _isMeaningful(v))
                    .map(([k, v]) => (
                      <Row key={k} label={k.replace(/_/g, ' ')} value={v} t={t} />
                    ))}
                </div>
              ))
            ) : (
              Object.entries(pickup)
                .filter(([, v]) => _isMeaningful(v))
                .map(([k, v]) => <Row key={k} label={k.replace(/_/g, ' ')} value={v} t={t} />)
            )}
          </CardContent>
        </Card>
      )}

      {hasVisit && (
        <Card className="glassmorphism" data-testid="listing-visit-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Calendar className="h-4 w-4 text-emerald-600" />
              {t('listingDetail.visitTitle', 'Visit Before Bidding')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 pt-0">
            <Row label={t('listingDetail.visitOffered', 'Visits offered')} value={!!visit.offered} t={t} />
            <Row label={t('listingDetail.visitDates', 'Available dates')} value={visit.dates} t={t} />
            <Row label={t('listingDetail.visitInstructions', 'Instructions')} value={visit.instructions} t={t} />
            <Row label={t('listingDetail.visitAddress', 'Address')} value={visit.address} t={t} />
            <Row label={t('listingDetail.visitContact', 'Contact')} value={visit.contact} t={t} />
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ListingLogisticsDetails;
