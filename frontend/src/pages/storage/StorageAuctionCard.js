import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge } from '../../components/ui/badge';
import { Gavel, MapPin, Layers, Clock } from 'lucide-react';
import StorageCountdown from './StorageCountdown';

const PROVINCE_FLAG = '🇨🇦';

/**
 * Auction card for the browse grid. Tailwind-only; no CSS file needed.
 */
const StorageAuctionCard = ({ auction }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  const photo = (auction.photos || [])[0];
  const endingSoon =
    auction.live_status === 'active' &&
    new Date(auction.end_time).getTime() - Date.now() < 60 * 60 * 1000;
  const isLive = auction.live_status === 'active';

  return (
    <Link
      to={`/storage-auctions/${auction.id}`}
      className="group relative block bg-white dark:bg-slate-800 rounded-2xl overflow-hidden shadow-md border border-slate-100 dark:border-slate-700 transition-all duration-300 hover:shadow-2xl hover:-translate-y-1 hover:border-blue-200 dark:hover:border-blue-700"
      data-testid={`storage-auction-card-${auction.id}`}
    >
      {/* Photo */}
      <div className="relative h-44 overflow-hidden bg-slate-200 dark:bg-slate-700">
        {photo ? (
          <img
            src={photo}
            alt={`Unit ${auction.unit_number}`}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-slate-400">
            <span className="text-5xl">🔒</span>
          </div>
        )}
        {endingSoon && (
          <div
            className="absolute top-3 left-3 bg-red-500 text-white text-[10px] font-bold px-2.5 py-1 rounded-full animate-pulse"
            data-testid="storage-card-ending-soon"
          >
            ⏰ {isFr ? 'SE TERMINE BIENTÔT' : 'ENDING SOON'}
          </div>
        )}
        {isLive && !endingSoon && (
          <div className="absolute top-3 left-3 bg-emerald-500 text-white text-[10px] font-bold px-2.5 py-1 rounded-full flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
            LIVE
          </div>
        )}
        <div className="absolute top-3 right-3 bg-emerald-500 text-white text-[10px] font-bold px-2 py-1 rounded-full">
          💰 {isFr ? 'Sans frais' : 'No Buyer Fees'}
        </div>
      </div>

      {/* Body */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0">
            <p className="text-xs text-slate-500 flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {auction.facility_city}, {auction.facility_province} {PROVINCE_FLAG}
            </p>
            <h3 className="font-bold text-slate-900 dark:text-white truncate mt-0.5">
              Unit #{auction.unit_number} — {auction.unit_size}
            </h3>
            <p className="text-[11px] text-slate-400 capitalize">{auction.unit_type?.replace(/_/g, ' ')}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide">
              {isFr ? 'Offre actuelle' : 'Current Bid'}
            </p>
            <p className="text-2xl font-black text-blue-600">
              ${Number(auction.current_bid || 0).toLocaleString()}
            </p>
            <p className="text-[10px] text-slate-400">
              {auction.bid_count || 0} {isFr ? 'offres' : 'bids'}
            </p>
          </div>
        </div>

        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg px-3 py-2 mb-3 flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 flex items-center gap-1">
            <Clock className="h-3 w-3" /> {isFr ? 'Reste' : 'Ends'}
          </span>
          <StorageCountdown endTime={auction.end_time} compact />
        </div>

        {auction.is_lien_unit && (
          <Badge variant="outline" className="text-[10px] mb-2 border-amber-400 text-amber-700 bg-amber-50 dark:bg-amber-950/30">
            <Layers className="h-2.5 w-2.5 mr-1" />
            {isFr ? 'Unité sous droit de rétention' : 'Lien Unit'}
          </Badge>
        )}

        <div className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-xl text-center text-sm transition-colors flex items-center justify-center gap-1.5">
          <Gavel className="h-4 w-4" />
          {isFr ? 'Enchérir maintenant' : 'Bid Now'}
        </div>
      </div>
    </Link>
  );
};

export default StorageAuctionCard;
