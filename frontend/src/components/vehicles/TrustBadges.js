/**
 * TrustBadges.js
 * Trust and verification badges for vehicle auctions
 * Displays seller verification, title status, VIN checks, and ratings
 */

import React from 'react';
import { Badge } from '../ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import {
  Shield, ShieldCheck, CheckCircle, AlertTriangle, Star,
  Building2, User, Gavel, FileCheck, Car, Award,
  BadgeCheck, Clock, TrendingUp, Eye, Lock, Info
} from 'lucide-react';

// Seller Type Badge
export const SellerTypeBadge = ({ sellerType, size = 'default' }) => {
  const configs = {
    dealer: {
      icon: Building2,
      label: 'Licensed Dealer',
      color: 'bg-emerald-500 text-white',
      description: 'Verified licensed automotive dealer'
    },
    auctioneer: {
      icon: Gavel,
      label: 'Verified Auctioneer',
      color: 'bg-purple-500 text-white',
      description: 'Professional auction house'
    },
    private: {
      icon: User,
      label: 'Private Seller',
      color: 'bg-slate-500 text-white',
      description: 'Individual private seller'
    }
  };

  const config = configs[sellerType] || configs.private;
  const Icon = config.icon;
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'px-3 py-1';

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className={`${config.color} ${sizeClass} gap-1 cursor-help`} data-testid={`seller-type-badge-${sellerType}`}>
            <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'} />
            {config.label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// Verified Seller Badge
export const VerifiedSellerBadge = ({ isVerified, verificationDetails }) => {
  if (!isVerified) return null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className="bg-blue-500 text-white gap-1 cursor-help" data-testid="verified-seller-badge">
            <ShieldCheck className="h-4 w-4" />
            Verified Seller
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <div className="space-y-1">
            <p className="font-semibold">Verification Includes:</p>
            <ul className="text-sm space-y-0.5">
              <li className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-400" /> ID Verified
              </li>
              <li className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-400" /> Email Confirmed
              </li>
              <li className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-400" /> Phone Verified
              </li>
              {verificationDetails?.documentsVerified && (
                <li className="flex items-center gap-1">
                  <CheckCircle className="h-3 w-3 text-green-400" /> Documents Reviewed
                </li>
              )}
            </ul>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// Title Status Badge
export const TitleStatusBadge = ({ status, size = 'default' }) => {
  const configs = {
    clean: {
      icon: ShieldCheck,
      label: 'Clean Title',
      color: 'bg-green-500 text-white',
      bgLight: 'bg-green-100 text-green-800 border-green-200',
      description: 'No accidents, liens, or title issues reported'
    },
    salvage: {
      icon: AlertTriangle,
      label: 'Salvage Title',
      color: 'bg-red-500 text-white',
      bgLight: 'bg-red-100 text-red-800 border-red-200',
      description: 'Vehicle was previously declared a total loss'
    },
    rebuilt: {
      icon: Car,
      label: 'Rebuilt Title',
      color: 'bg-orange-500 text-white',
      bgLight: 'bg-orange-100 text-orange-800 border-orange-200',
      description: 'Previously salvaged, repaired and inspected'
    },
    flood: {
      icon: AlertTriangle,
      label: 'Flood Title',
      color: 'bg-red-600 text-white',
      bgLight: 'bg-red-100 text-red-800 border-red-200',
      description: 'Vehicle sustained flood or water damage'
    },
    lemon: {
      icon: AlertTriangle,
      label: 'Lemon Title',
      color: 'bg-yellow-500 text-white',
      bgLight: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      description: 'Manufacturer buyback due to defects'
    },
    unknown: {
      icon: Info,
      label: 'Unknown',
      color: 'bg-slate-400 text-white',
      bgLight: 'bg-slate-100 text-slate-700 border-slate-200',
      description: 'Title status not verified'
    }
  };

  const config = configs[status] || configs.unknown;
  const Icon = config.icon;
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'px-3 py-1';
  const colorClass = size === 'light' ? config.bgLight : config.color;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className={`${colorClass} ${sizeClass} gap-1 cursor-help border`} data-testid={`title-status-badge-${status}`}>
            <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'} />
            {config.label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// VIN Verified Badge
export const VINVerifiedBadge = ({ vinData, vin }) => {
  const isVerified = vinData && Object.keys(vinData).length > 0;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge 
            className={`gap-1 cursor-help ${isVerified ? 'bg-blue-100 text-blue-800 border-blue-200' : 'bg-slate-100 text-slate-600 border-slate-200'} border`}
            data-testid="vin-badge"
          >
            <FileCheck className="h-4 w-4" />
            VIN: {vin?.slice(0, 8)}...{vin?.slice(-4)}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <div className="space-y-2">
            <p className="font-semibold flex items-center gap-1">
              {isVerified ? (
                <><CheckCircle className="h-4 w-4 text-green-500" /> VIN Decoded Successfully</>
              ) : (
                <><Info className="h-4 w-4" /> VIN Not Decoded</>
              )}
            </p>
            {isVerified && vinData && (
              <div className="text-sm space-y-1">
                {vinData.make && <p>Make: {vinData.make}</p>}
                {vinData.model && <p>Model: {vinData.model}</p>}
                {vinData.year && <p>Year: {vinData.year}</p>}
                {vinData.engine && <p>Engine: {vinData.engine}</p>}
                {vinData.plant_country && <p>Manufactured: {vinData.plant_country}</p>}
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// Seller Rating Badge
export const SellerRatingBadge = ({ rating, reviewCount, totalSold }) => {
  const getStarColor = (rating) => {
    if (rating >= 4.5) return 'text-yellow-500';
    if (rating >= 4.0) return 'text-yellow-400';
    if (rating >= 3.0) return 'text-orange-400';
    return 'text-slate-400';
  };

  if (!rating && !totalSold) return null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-2 cursor-help" data-testid="seller-rating">
            {rating > 0 && (
              <div className="flex items-center gap-1">
                <Star className={`h-4 w-4 fill-current ${getStarColor(rating)}`} />
                <span className="font-semibold">{rating.toFixed(1)}</span>
              </div>
            )}
            {reviewCount > 0 && (
              <span className="text-sm text-slate-500">({reviewCount} reviews)</span>
            )}
            {totalSold > 0 && (
              <Badge variant="outline" className="text-xs">
                {totalSold} sold
              </Badge>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="space-y-1">
            <p className="font-semibold">Seller Performance</p>
            {rating > 0 && <p>Average Rating: {rating.toFixed(1)}/5</p>}
            {reviewCount > 0 && <p>Total Reviews: {reviewCount}</p>}
            {totalSold > 0 && <p>Vehicles Sold: {totalSold}</p>}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// Reserve Status Badge
export const ReserveStatusBadge = ({ reserveMet, hasReserve }) => {
  if (!hasReserve) return null;

  return (
    <Badge 
      className={`gap-1 ${reserveMet 
        ? 'bg-green-100 text-green-800 border-green-300' 
        : 'bg-amber-100 text-amber-800 border-amber-300'} border`}
      data-testid="reserve-status-badge"
    >
      {reserveMet ? (
        <>
          <CheckCircle className="h-4 w-4" />
          Reserve Met
        </>
      ) : (
        <>
          <AlertTriangle className="h-4 w-4" />
          Reserve Not Met
        </>
      )}
    </Badge>
  );
};

// Running Status Badge
export const RunningStatusBadge = ({ isRunning }) => {
  return (
    <Badge 
      className={`gap-1 ${isRunning 
        ? 'bg-green-100 text-green-800 border-green-200' 
        : 'bg-red-100 text-red-800 border-red-200'} border`}
      data-testid="running-status-badge"
    >
      {isRunning ? (
        <>
          <CheckCircle className="h-4 w-4" />
          Running & Drives
        </>
      ) : (
        <>
          <AlertTriangle className="h-4 w-4" />
          Non-Running
        </>
      )}
    </Badge>
  );
};

// Live Auction Badge
export const LiveAuctionBadge = () => (
  <Badge className="bg-red-500 text-white animate-pulse gap-1" data-testid="live-auction-badge">
    <div className="w-2 h-2 bg-white rounded-full animate-ping" />
    LIVE
  </Badge>
);

// Ending Soon Badge
export const EndingSoonBadge = ({ timeRemaining }) => {
  if (!timeRemaining || timeRemaining.days > 0 || timeRemaining.hours > 1) return null;

  return (
    <Badge className="bg-orange-500 text-white animate-pulse gap-1" data-testid="ending-soon-badge">
      <Clock className="h-4 w-4" />
      Ending Soon
    </Badge>
  );
};

// No Reserve Badge
export const NoReserveBadge = () => (
  <Badge className="bg-emerald-500 text-white gap-1" data-testid="no-reserve-badge">
    <Award className="h-4 w-4" />
    No Reserve
  </Badge>
);

// Combined Trust Indicators Component
export const TrustIndicators = ({ 
  seller, 
  vehicle, 
  compact = false,
  showAll = true 
}) => {
  if (compact) {
    return (
      <div className="flex flex-wrap gap-1.5" data-testid="trust-indicators-compact">
        {seller?.verification_status === 'approved' && (
          <Badge className="bg-blue-100 text-blue-700 text-xs gap-1">
            <BadgeCheck className="h-3 w-3" /> Verified
          </Badge>
        )}
        {vehicle?.title_status === 'clean' && (
          <Badge className="bg-green-100 text-green-700 text-xs gap-1">
            <Shield className="h-3 w-3" /> Clean Title
          </Badge>
        )}
        {vehicle?.condition_report?.is_running && (
          <Badge className="bg-emerald-100 text-emerald-700 text-xs gap-1">
            <CheckCircle className="h-3 w-3" /> Running
          </Badge>
        )}
        {!vehicle?.reserve_price && (
          <Badge className="bg-purple-100 text-purple-700 text-xs gap-1">
            <Award className="h-3 w-3" /> No Reserve
          </Badge>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="trust-indicators">
      {/* Seller Info Row */}
      <div className="flex flex-wrap gap-2 items-center">
        <SellerTypeBadge sellerType={seller?.seller_type} />
        <VerifiedSellerBadge 
          isVerified={seller?.verification_status === 'approved'} 
          verificationDetails={seller}
        />
        <SellerRatingBadge 
          rating={seller?.average_rating} 
          reviewCount={seller?.review_count}
          totalSold={seller?.total_sold}
        />
      </div>

      {/* Vehicle Status Row */}
      {showAll && (
        <div className="flex flex-wrap gap-2 items-center">
          <TitleStatusBadge status={vehicle?.title_status} />
          <VINVerifiedBadge vin={vehicle?.vin} vinData={vehicle?.vin_data} />
          <RunningStatusBadge isRunning={vehicle?.condition_report?.is_running} />
        </div>
      )}

      {/* Auction Status Row */}
      {showAll && (
        <div className="flex flex-wrap gap-2 items-center">
          {!vehicle?.reserve_price && <NoReserveBadge />}
          {vehicle?.reserve_price && (
            <ReserveStatusBadge 
              hasReserve={!!vehicle?.reserve_price} 
              reserveMet={vehicle?.reserve_met} 
            />
          )}
        </div>
      )}
    </div>
  );
};

// Subscription Tier Badge
export const SubscriptionBadge = ({ tier }) => {
  const configs = {
    free: { label: 'Standard', color: 'bg-slate-100 text-slate-600' },
    premium: { label: 'Premium', color: 'bg-blue-100 text-blue-700' },
    vip: { label: 'VIP Elite', color: 'bg-amber-100 text-amber-700' }
  };

  const config = configs[tier] || configs.free;

  return (
    <Badge className={`${config.color} gap-1`} data-testid="subscription-badge">
      {tier === 'vip' && <Award className="h-3 w-3" />}
      {config.label}
    </Badge>
  );
};

export default TrustIndicators;
