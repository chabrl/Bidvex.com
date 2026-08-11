import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { DollarSign, Gavel, Trophy, Heart, TrendingUp, TrendingDown, Eye, AlertTriangle, Clock, Lock, CreditCard, ShieldCheck, KeyRound } from 'lucide-react';
import { toast } from 'sonner';
import Countdown from 'react-countdown';
import { formatCurrency } from '../utils/currencyFormatter';
import { LoadingTimeout } from '../components/LoadingTimeout';
import { BuyerEscrowPanel } from '../components/EscrowPickupPanel';
// iter300 P2 — "Sellers I Follow" tab
import { FollowedSellersList } from '../components/FollowedSellersList';
import InfoTip from '../components/InfoTip';
import PendingPaymentsCard from '../components/PendingPaymentsCard';
// iter302 Directive 2 — buyer Settle Payment flow
import SettlePaymentModal from '../components/SettlePaymentModal';

const API = API_BASE;

const BuyerDashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/buyer`, { timeout: 15000 });
      setDashboard(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <LoadingTimeout rows={6} variant="cards" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="buyer-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* iter261 — Pending payments anchored at the very top. */}
        <PendingPaymentsCard />
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold mb-2">{t('dashboard.buyer.title')}</h1>
            <p className="text-muted-foreground">{t('dashboard.buyer.trackBidsWins')}</p>
          </div>
          <InfoTip
            en="Your buyer dashboard. See active bids, items you've won, and your watchlist all in one place. Bids hold a payment authorization on your card — never a charge."
            fr="Votre tableau de bord acheteur. Consultez vos enchères actives, vos articles gagnés et votre liste de surveillance au même endroit. Une enchère retient une autorisation sur votre carte — jamais un débit."
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-6">
          <StatCard
            icon={<Gavel className="h-6 w-6" />}
            title={t('dashboard.buyer.activeBids')}
            value={dashboard?.active_bids || 0}
            color="blue"
            tip={{
              en: "Number of auctions where you currently hold the highest bid or are still actively bidding.",
              fr: "Nombre d'enchères où vous détenez actuellement la mise la plus élevée ou enchérissez encore activement.",
            }}
          />
          <StatCard
            icon={<TrendingUp className="h-6 w-6" />}
            title={t('dashboard.buyer.winning', 'Winning')}
            value={dashboard?.winning_bids || 0}
            color="emerald"
            tip={{
              en: "Live auctions where you are currently the highest bidder.",
              fr: "Enchères en cours où vous êtes actuellement le plus offrant.",
            }}
          />
          <StatCard
            icon={<Trophy className="h-6 w-6" />}
            title={t('dashboard.buyer.wonItems')}
            value={dashboard?.won_items || 0}
            color="green"
            tip={{
              en: "Auctions you have won. Pay the seller within the deadline to complete your purchase.",
              fr: "Enchères que vous avez remportées. Payez le vendeur avant la date limite pour finaliser votre achat.",
            }}
          />
          <StatCard
            icon={<TrendingDown className="h-6 w-6" />}
            title={t('dashboard.buyer.lostBids', 'Lost')}
            value={dashboard?.lost_bids || 0}
            color="red"
            tip={{
              en: "Ended auctions where you bid but didn't win.",
              fr: "Enchères terminées où vous avez misé sans gagner.",
            }}
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title="Total Bids"
            value={dashboard?.total_bids || 0}
            color="purple"
            tip={{
              en: "Lifetime number of bids you've placed across all auctions on BidVex.",
              fr: "Nombre total d'enchères que vous avez placées sur toutes les ventes BidVex.",
            }}
          />
        </div>

        {/* iter298 BUG 4/5 — My Purchases: won items with payment status,
            pickup status, and itemized receipts. */}
        <PurchasesAndReceiptsCard wonItems={dashboard?.won_items_detail || []} onRefresh={fetchDashboard} />

        {/* iter298 BUG 5 — Active deposits with status + refund timeline. */}
        <DepositsCard deposits={dashboard?.deposits || []} />

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {t('dashboard.buyer.myBidsTitle')}
              <InfoTip
                en="All your bids — winning, outbid, and watched. Use the tabs to filter. Bids cannot be cancelled once placed."
                fr="Toutes vos enchères — gagnantes, surenchéries et surveillées. Utilisez les onglets pour filtrer. Une enchère ne peut être annulée une fois placée."
              />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="all" className="space-y-4">
              <TabsList className="flex w-full bg-transparent overflow-x-auto scrollbar-hide">
                <TabsTrigger value="all" className="flex-shrink-0 min-w-[80px] bg-transparent">{t('dashboard.buyer.allBids')}</TabsTrigger>
                <TabsTrigger value="winning" className="flex-shrink-0 min-w-[80px] bg-transparent text-green-600">{t('dashboard.buyer.winning')}</TabsTrigger>
                <TabsTrigger value="losing" className="flex-shrink-0 min-w-[80px] bg-transparent text-red-600">{t('dashboard.buyer.outbid')}</TabsTrigger>
                <TabsTrigger value="watching" className="flex-shrink-0 min-w-[80px] bg-transparent">{t('watchlist.title', 'Watching')}</TabsTrigger>
                <TabsTrigger value="escrow" className="flex-shrink-0 min-w-[80px] bg-transparent" data-testid="buyer-escrow-tab">
                  <Lock className="h-3 w-3 mr-1 inline" /> {t('dashboard.buyer.escrow', 'Escrow')}
                </TabsTrigger>
                <TabsTrigger value="following" className="flex-shrink-0 min-w-[80px] bg-transparent" data-testid="buyer-following-tab">
                  {t('dashboard.buyer.following', 'Following')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="all">
                <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
                  <span>{t('dashboard.buyer.allBidsHint', 'All auctions you have placed bids on.')}</span>
                  <InfoTip
                    en="Green = you're winning. Red = someone outbid you. Click any item to bid again."
                    fr="Vert = vous gagnez. Rouge = quelqu'un a surenchéri. Cliquez sur un article pour enchérir à nouveau."
                  />
                </div>
                {dashboard?.bids && dashboard.bids.length > 0 ? (
                  <div
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                    data-testid="buyer-bids-grid-all"
                  >
                    {dashboard.bids.map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      // iter367 P0 — Backend now emits a canonical bid_status
                      // (winning | outbid | won | lost | ended_no_listing) plus
                      // enriched fallbacks (_won_auction, _receipt) so cards
                      // render correctly even when the source listing was
                      // purged post-settlement. Prevents "OUTBID $0.00" bug.
                      const bidStatus = bid.bid_status || (listing && listing.current_price === bid.amount ? 'winning' : 'outbid');
                      const wonAuction = bid._won_auction;
                      const receipt = bid._receipt;
                      const isWinning = bidStatus === 'winning';
                      const isWon = bidStatus === 'won';
                      const isLost = bidStatus === 'lost' || bidStatus === 'ended_no_listing';
                      const isOutbid = bidStatus === 'outbid';
                      const auctionEndDate = listing?.auction_end_date ? new Date(listing.auction_end_date) : null;
                      const isEnded = !listing || (auctionEndDate && new Date() > auctionEndDate);
                      const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
                      const isUrgent = timeLeft > 0 && timeLeft < 3600000; // Less than 1 hour
                      const displayTitle = listing?.title || wonAuction?.listing_title || receipt?.listing_title || 'Auction item';
                      const displayImage = listing?.images?.[0] || wonAuction?.listing_image;
                      const displayCurrentPrice = listing?.current_price ?? wonAuction?.winning_bid ?? receipt?.hammer_price ?? bid.amount;
                      const borderColor = isWinning || isWon ? 'border-green-500' : (isLost || isOutbid ? 'border-red-300' : 'border-gray-200 dark:border-gray-700');

                      return (
                        <Card key={bid.id} className={`overflow-hidden border-2 ${borderColor}`} data-testid={`bid-card-${bid.id}`}>
                          {/* Status Badge - Top Left - Larger & More Prominent */}
                          <div className="relative">
                            <div className="absolute top-3 left-3 z-10">
                              {isWinning ? (
                                <Badge className="bg-green-600 text-white border-0 text-base px-4 py-2 font-bold shadow-lg" data-testid="bid-status-winning">
                                  <TrendingUp className="h-5 w-5 mr-1.5" />
                                  WINNING
                                </Badge>
                              ) : isWon ? (
                                <Badge className="bg-emerald-600 text-white border-0 text-base px-4 py-2 font-bold shadow-lg" data-testid="bid-status-won">
                                  <Trophy className="h-5 w-5 mr-1.5" />
                                  WON
                                </Badge>
                              ) : isLost ? (
                                <Badge className="bg-slate-500 text-white border-0 text-base px-4 py-2 font-bold shadow-lg" data-testid="bid-status-ended">
                                  ENDED
                                </Badge>
                              ) : (
                                <Badge className="bg-red-600 text-white border-0 text-base px-4 py-2 font-bold shadow-lg" data-testid="bid-status-outbid">
                                  <TrendingDown className="h-5 w-5 mr-1.5" />
                                  OUTBID
                                </Badge>
                              )}
                            </div>

                            {/* Countdown - Top Right */}
                            {auctionEndDate && !isEnded && (
                              <div className="absolute top-3 right-3 z-10">
                                <Badge className={`${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white border-0 text-sm px-3 py-1.5 shadow-lg`}>
                                  <Clock className="h-4 w-4 mr-1" />
                                  <Countdown
                                    date={auctionEndDate}
                                    renderer={({ days, hours, minutes }) => (
                                      <span className="font-bold">{days}d {hours}h {minutes}m</span>
                                    )}
                                  />
                                </Badge>
                              </div>
                            )}

                            {/* Image */}
                            <div className="w-full h-48 bg-gray-100">
                              {displayImage ? (
                                <img src={displayImage} alt={displayTitle} className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
                              )}
                            </div>
                          </div>

                          {/* Content Section */}
                          <CardContent className="p-4 space-y-4">
                            <h3 className="font-bold text-xl line-clamp-2">{displayTitle}</h3>

                            {/* Bid Comparison - Clear Layout with Better Visual Hierarchy */}
                            <div className={`grid grid-cols-2 gap-4 p-4 rounded-lg ${(isWinning || isWon) ? 'bg-green-50 dark:bg-green-950/30' : 'bg-red-50 dark:bg-red-950/30'}`}>
                              <div>
                                <p className="text-xs text-muted-foreground uppercase mb-1 font-semibold">{t('dashboard.buyer.yourBid')}</p>
                                <p className="text-2xl font-bold">{formatCurrency(bid.amount)}</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground uppercase mb-1 font-semibold">
                                  {isWon ? t('dashboard.buyer.finalPrice', 'Won at') : (isLost ? t('dashboard.buyer.finalPriceLost', 'Ended at') : 'Current Price')}
                                </p>
                                <p className={`text-2xl font-bold ${(isWinning || isWon) ? 'text-green-600' : 'text-red-600'}`}>{formatCurrency(displayCurrentPrice)}</p>
                              </div>
                            </div>

                            {/* Additional Info */}
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Badge variant="outline">{listing?.bid_count || 0} bids</Badge>
                              {isEnded && <Badge variant="destructive">{t("auction.auctionEnded")}</Badge>}
                              {isWon && receipt?.pickup_code && (
                                <Badge className="bg-emerald-100 text-emerald-800">Pickup: {receipt.pickup_code}</Badge>
                              )}
                            </div>
                          </CardContent>

                          {/* Action Buttons - Full Width on Mobile */}
                          <CardFooter className="p-4 pt-0 gap-2 flex-col sm:flex-row">
                            <Button
                              variant="outline"
                              className="w-full sm:flex-1"
                              onClick={() => navigate(`/listing/${bid.listing_id}`)}
                              disabled={isEnded && !listing}
                              title={isEnded && !listing ? 'Listing archived' : ''}
                            >
                              View Listing
                            </Button>
                            {!isWinning && !isWon && !isEnded && (
                              <Button
                                className="w-full sm:flex-1 gradient-button text-white border-0 font-semibold"
                                onClick={() => navigate(`/listing/${bid.listing_id}`)}
                              >
                                {t('buyerDash.placeHigherBid')}
                              </Button>
                            )}
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-primary/10 to-accent/10 rounded-full flex items-center justify-center">
                        <Gavel className="h-10 w-10 text-primary" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">{t('buyerDash.noActiveBids')}</h3>
                        <p className="text-muted-foreground">{t('buyerDash.startBidding')}</p>
                      </div>
                      <Button className="gradient-button text-white border-0" onClick={() => navigate('/marketplace')}>
                        Browse Marketplace
                      </Button>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="winning">
                {dashboard?.bids?.filter(bid => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  return listing && listing.current_price === bid.amount;
                }).length > 0 ? (
                  <div
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                    data-testid="buyer-bids-grid-winning"
                  >
                    {dashboard.bids.filter(bid => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return listing && listing.current_price === bid.amount;
                    }).map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      const auctionEndDate = listing ? new Date(listing.auction_end_date) : null;
                      const isEnded = auctionEndDate && new Date() > auctionEndDate;
                      const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
                      const isUrgent = timeLeft > 0 && timeLeft < 3600000;

                      return (
                        <Card key={bid.id} className="border-2 border-green-500 overflow-hidden shadow-lg">
                          <div className="relative h-32 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-950 dark:to-green-900 flex items-center justify-center">
                            <Badge className="absolute top-3 left-3 bg-green-600 text-white text-base px-4 py-2 font-bold shadow-lg">
                              <Trophy className="h-5 w-5 mr-1.5" />
                              WINNING
                            </Badge>
                            {auctionEndDate && !isEnded && (
                              <Badge className={`absolute top-3 right-3 ${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white text-sm px-3 py-1.5 shadow-lg`}>
                                <Clock className="h-4 w-4 mr-1" />
                                <Countdown
                                  date={auctionEndDate}
                                  renderer={({ days, hours, minutes }) => (
                                    <span className="font-bold">{days}d {hours}h {minutes}m</span>
                                  )}
                                />
                              </Badge>
                            )}
                            <TrendingUp className="h-16 w-16 text-green-600 opacity-20" />
                          </div>
                          <CardContent className="p-4 space-y-3">
                            <h3 className="font-bold text-lg">{listing?.title}</h3>
                            <div className="flex items-center justify-between p-4 bg-green-50 dark:bg-green-950 rounded-lg">
                              <div>
                                <p className="text-xs text-muted-foreground uppercase font-semibold mb-1">{t('buyerDash.yourWinningBid')}</p>
                                <p className="text-3xl font-bold text-green-600">{formatCurrency(bid.amount)}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{listing?.bid_count || 0} bids</Badge>
                              {isEnded && <Badge className="bg-green-600 text-white">Won!</Badge>}
                            </div>

                            {/* Post-Sale Contact Info — Seller */}
                            {listing?.status === 'sold' && listing?.seller_contact && (
                              <div className="mt-2 p-4 rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800" data-testid={`contact-seller-${listing.id}`}>
                                <p className="text-xs uppercase font-semibold text-blue-800 dark:text-blue-300 mb-2">Contact Seller / Contacter le vendeur</p>
                                <dl className="text-sm space-y-1">
                                  <div className="flex justify-between"><dt className="text-muted-foreground">Name</dt><dd className="font-medium">{listing.seller_contact.name || '—'}</dd></div>
                                  <div className="flex justify-between"><dt className="text-muted-foreground">Email</dt><dd className="font-medium"><a className="text-blue-600 hover:underline" href={`mailto:${listing.seller_contact.email}`}>{listing.seller_contact.email || '—'}</a></dd></div>
                                  <div className="flex justify-between"><dt className="text-muted-foreground">Phone</dt><dd className="font-medium">{listing.seller_contact.phone ? <a className="text-blue-600 hover:underline" href={`tel:${listing.seller_contact.phone}`}>{listing.seller_contact.phone}</a> : '—'}</dd></div>
                                </dl>
                              </div>
                            )}
                          </CardContent>
                          <CardFooter className="p-4 pt-0 flex-col sm:flex-row gap-2">
                            <Button className="w-full sm:flex-1" variant="outline" onClick={() => navigate(`/listing/${bid.listing_id}`)}>
                              {t('buyerDash.viewListingDetails')}
                            </Button>
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-green-100 to-green-50 dark:from-green-950 dark:to-green-900 rounded-full flex items-center justify-center">
                        <Trophy className="h-10 w-10 text-green-600" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">{t('buyerDash.noWinningBids')}</h3>
                        <p className="text-muted-foreground">{t('buyerDash.keepBidding')}</p>
                      </div>
                      <Button className="gradient-button text-white border-0" onClick={() => navigate('/marketplace')}>
                        Browse Marketplace
                      </Button>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="losing">
                {dashboard?.bids?.filter(bid => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  return listing && listing.current_price > bid.amount;
                }).length > 0 ? (
                  <div
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                    data-testid="buyer-bids-grid-outbid"
                  >
                    {dashboard.bids.filter(bid => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return listing && listing.current_price > bid.amount;
                    }).map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      const auctionEndDate = listing ? new Date(listing.auction_end_date) : null;
                      const isEnded = auctionEndDate && new Date() > auctionEndDate;
                      const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
                      const isUrgent = timeLeft > 0 && timeLeft < 3600000;

                      return (
                        <Card key={bid.id} className="border-2 border-red-500 overflow-hidden shadow-lg">
                          <div className="relative h-32 bg-gradient-to-br from-red-50 to-red-100 dark:from-red-950 dark:to-red-900 flex items-center justify-center">
                            <Badge className="absolute top-3 left-3 bg-red-600 text-white text-base px-4 py-2 font-bold shadow-lg">
                              <TrendingDown className="h-5 w-5 mr-1.5" />
                              OUTBID
                            </Badge>
                            {auctionEndDate && !isEnded && (
                              <Badge className={`absolute top-3 right-3 ${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white text-sm px-3 py-1.5 shadow-lg`}>
                                <Clock className="h-4 w-4 mr-1" />
                                <Countdown
                                  date={auctionEndDate}
                                  renderer={({ days, hours, minutes }) => (
                                    <span className="font-bold">{days}d {hours}h {minutes}m</span>
                                  )}
                                />
                              </Badge>
                            )}
                            <AlertTriangle className="h-16 w-16 text-red-600 opacity-20" />
                          </div>
                          <CardContent className="p-4 space-y-3">
                            <h3 className="font-bold text-lg">{listing?.title}</h3>
                            <div className="grid grid-cols-2 gap-4">
                              <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                                <p className="text-xs text-muted-foreground uppercase mb-1 font-semibold">{t('dashboard.buyer.yourBid')}</p>
                                <p className="text-xl font-bold">{formatCurrency(bid.amount)}</p>
                              </div>
                              <div className="p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                                <p className="text-xs text-muted-foreground uppercase mb-1 font-semibold">Current Bid</p>
                                <p className="text-xl font-bold text-red-600">{formatCurrency(listing?.current_price)}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{listing?.bid_count || 0} bids</Badge>
                              {isEnded && <Badge variant="destructive">{t("auction.auctionEnded")}</Badge>}
                            </div>
                          </CardContent>
                          <CardFooter className="p-4 pt-0 flex-col sm:flex-row gap-2">
                            {!isEnded ? (
                              <Button className="w-full gradient-button text-white border-0 font-semibold" onClick={() => navigate(`/listing/${bid.listing_id}`)}>
                                {t('buyerDash.placeHigherBidNow')}
                              </Button>
                            ) : (
                              <Button className="w-full" variant="outline" onClick={() => navigate(`/listing/${bid.listing_id}`)}>
                                View Listing
                              </Button>
                            )}
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-blue-100 to-blue-50 dark:from-blue-950 dark:to-blue-900 rounded-full flex items-center justify-center">
                        <TrendingUp className="h-10 w-10 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">{t('buyerDash.allBidsLeading')}</h3>
                        <p className="text-muted-foreground">{t('buyerDash.greatJob')}</p>
                      </div>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="watching">
                <Card className="p-8">
                  <div className="text-center space-y-6">
                    <div className="w-20 h-20 mx-auto bg-gradient-to-br from-pink-100 to-red-50 dark:from-pink-950 dark:to-red-900 rounded-full flex items-center justify-center">
                      <Heart className="h-10 w-10 text-pink-600 fill-pink-600" />
                    </div>
                    <div>
                      <h3 className="text-2xl font-semibold mb-2">{t('buyerDash.viewYourWatchlist')}</h3>
                      <p className="text-muted-foreground max-w-md mx-auto">
                        {t('buyerDash.watchlistDesc')}
                      </p>
                    </div>
                    <div className="flex gap-3 justify-center">
                      <Button 
                        className="gradient-button text-white border-0 px-8" 
                        onClick={() => navigate('/watchlist')}
                        size="lg"
                      >
                        <Heart className="h-5 w-5 mr-2 fill-white" />
                        {t('buyerDash.viewMyWatchlist')}
                      </Button>
                      <Button 
                        variant="outline" 
                        onClick={() => navigate('/lots')}
                        size="lg"
                      >
                        Browse Auctions
                      </Button>
                    </div>
                  </div>
                </Card>
              </TabsContent>

              <TabsContent value="escrow" data-testid="buyer-escrow-content">
                <BuyerEscrowPanel />
              </TabsContent>

              <TabsContent value="following" data-testid="buyer-following-content">
                <FollowedSellersList />
              </TabsContent>

             </Tabs>
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>{t("dashboard.buyer.purchaseHistory")}</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.bids && dashboard.bids.length > 0 ? (
              <div className="space-y-4">
                {dashboard.bids.slice(0, 5).map((bid) => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  if (!listing) return null;
                  
                  return (
                    <div
                      key={bid.id}
                      className="flex flex-col sm:flex-row gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                      data-testid={`bid-item-${bid.id}`}
                    >
                      <div className="w-full sm:w-24 h-24 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                        {listing.images && listing.images[0] ? (
                          <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">📦</div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3 className="font-semibold truncate">{listing.title}</h3>
                          <Badge variant={listing.status === 'active' ? 'default' : 'secondary'}>
                            {listing.status}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-2">
                          <span>Your Bid: {formatCurrency(bid.amount)}</span>
                          <span>Current: {formatCurrency(listing.current_price)}</span>
                          {bid.amount >= listing.current_price && listing.status === 'active' && (
                            <Badge variant="default" className="text-xs">Winning</Badge>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/listing/${listing.id}`)}
                        >
                          View Listing
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <Gavel className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">{t('buyerDash.noBidsYet')}</p>
                <Button onClick={() => navigate('/marketplace')} className="gradient-button text-white border-0">
                  Start Bidding
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, title, value, color, tip }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
        {tip && <InfoTip en={tip.en} fr={tip.fr} />}
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
    </CardContent>
  </Card>
);

export default BuyerDashboard;

// ========== iter298 BUG 4/5 — My Purchases → Receipts ==========
const PAYMENT_BADGES = {
  payment_collected: { en: 'Paid', fr: 'Payé', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  pending_payment: { en: 'Payment due', fr: 'Paiement dû', cls: 'bg-amber-100 text-amber-800 border-amber-300' },
  payment_failed: { en: 'Payment failed', fr: 'Paiement échoué', cls: 'bg-red-100 text-red-800 border-red-300' },
  overdue: { en: 'Overdue', fr: 'En retard', cls: 'bg-red-100 text-red-800 border-red-300' },
};

const PurchasesAndReceiptsCard = ({ wonItems, onRefresh }) => {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const fr = (i18n.language || 'en').startsWith('fr');
  const [receipts, setReceipts] = useState(null);
  const [showReceipts, setShowReceipts] = useState(false);
  // iter302 Directive 2 — listing currently being settled (modal target)
  const [settleFor, setSettleFor] = useState(null);

  useEffect(() => {
    axios.get(`${API}/receipts/mine`, { params: { role: 'buyer' } })
      .then((r) => setReceipts(r.data?.receipts || []))
      .catch(() => setReceipts([]));
  }, []);

  if (!wonItems.length && !(receipts || []).length) return null;

  return (
    <Card className="glassmorphism" data-testid="buyer-purchases-card">
      <CardHeader>
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-500" />
            {fr ? 'Mes achats' : 'My Purchases'}
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowReceipts((v) => !v)}
            data-testid="toggle-receipts-btn"
          >
            {fr ? 'Reçus' : 'Receipts'} ({(receipts || []).length})
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {wonItems.map((w) => {
          const badge = PAYMENT_BADGES[w.payment_status] || PAYMENT_BADGES.pending_payment;
          // iter471 — Compose a stable de-duplicated key that mirrors
          // the backend's (section, listing_id, lot_number) identity so
          // React never keys two distinct purchase rows on the same
          // listing_id (multi-lot wins by the same buyer).
          const rowKey = `${w.section || 'sec'}::${w.listing_id}::${w.lot_number ?? '0'}`;
          const isMultiLot = w.lot_number !== null && w.lot_number !== undefined;
          const primaryTitle = isMultiLot
            ? `${fr ? 'Lot' : 'Lot'} #${w.lot_number}${w.lot_title ? ' · ' + w.lot_title : ''}`
            : (w.title || (fr ? 'Article' : 'Item'));
          const secondaryParent = isMultiLot ? (w.parent_listing_title || w.title) : null;
          const displayAmount = w.total_charged != null && w.total_charged > 0
            ? w.total_charged
            : w.final_price;
          return (
            <div
              key={rowKey}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 border rounded-lg"
              data-testid={`won-item-${w.listing_id}${isMultiLot ? '-lot' + w.lot_number : ''}`}
              data-section={w.section || 'marketplace'}
              data-lot-number={w.lot_number ?? ''}
            >
              <div className="min-w-0">
                <p className="font-semibold text-sm truncate" data-testid={`purchase-primary-title-${rowKey}`}>
                  {primaryTitle}
                </p>
                {secondaryParent && (
                  <p
                    className="text-xs text-muted-foreground truncate"
                    data-testid={`purchase-parent-${rowKey}`}
                  >
                    {fr ? 'Enchère' : 'Auction'}: {secondaryParent}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  {formatCurrency(displayAmount)} {w.currency || 'CAD'}
                  {w.sold_at ? ` · ${new Date(w.sold_at).toLocaleDateString()}` : ''}
                </p>
                <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                  {w.quantity != null && Number(w.quantity) > 0 && (
                    <Badge
                      variant="outline"
                      className="text-[10px] py-0 h-5"
                      data-testid={`purchase-qty-${rowKey}`}
                    >
                      {fr ? 'Qté' : 'Qty'}: {w.quantity}
                    </Badge>
                  )}
                  {w.order_number && (
                    <Badge
                      variant="outline"
                      className="text-[10px] py-0 h-5 font-mono"
                      data-testid={`purchase-order-${rowKey}`}
                    >
                      {fr ? 'Cmd' : 'Order'}: {w.order_number}
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge className={`border text-xs ${badge.cls}`} data-testid={`payment-status-${w.listing_id}${isMultiLot ? '-lot' + w.lot_number : ''}`}>
                  {fr ? badge.fr : badge.en}
                </Badge>
                {w.pickup_confirmed ? (
                  <Badge className="border text-xs bg-cyan-100 text-cyan-800 border-cyan-300">
                    {fr ? 'Ramassage confirmé' : 'Pickup confirmed'}
                  </Badge>
                ) : (
                  <Badge className="border text-xs bg-slate-100 text-slate-600 border-slate-300">
                    {fr ? 'Ramassage en attente' : 'Pickup pending'}
                  </Badge>
                )}
                {/* iter302 Directive 2 — Settle Payment (charges the saved
                    card off-session through /api/settlement/settle). */}
                {['pending_payment', 'payment_failed', 'overdue'].includes(w.payment_status) && (
                  <Button
                    size="sm"
                    className="h-7 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-full px-3"
                    onClick={() => setSettleFor(w.listing_id)}
                    data-testid={`settle-payment-btn-${w.listing_id}${isMultiLot ? '-lot' + w.lot_number : ''}`}
                  >
                    <CreditCard className="h-3.5 w-3.5 mr-1" />
                    {fr ? 'Régler le paiement' : 'Settle Payment'}
                  </Button>
                )}
                {/* iter302 Directive 2 — pickup code, winner-only surface */}
                {w.payment_status === 'payment_collected' && w.pickup_code && (
                  <Badge
                    className="border text-xs bg-indigo-100 text-indigo-800 border-indigo-300 font-mono"
                    data-testid={`pickup-code-${w.listing_id}${isMultiLot ? '-lot' + w.lot_number : ''}`}
                  >
                    <KeyRound className="h-3 w-3 mr-1" />
                    {fr ? 'Code' : 'Code'}: {w.pickup_code}
                  </Badge>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigate(`/listing/${w.listing_id}`)}
                >
                  <Eye className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          );
        })}

        {/* iter302 — escrow clarity trust line (display only) */}
        {wonItems.length > 0 && (
          <p className="text-xs text-muted-foreground flex items-center gap-1.5 pt-2 border-t" data-testid="escrow-clarity-note">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0" />
            {fr
              ? "Les fonds sont détenus par BidVex Inc. jusqu'à la confirmation de la collecte"
              : 'Funds are held securely by BidVex Inc. until pickup is confirmed'}
          </p>
        )}

        {/* iter302 Directive 2 — Settle Payment modal */}
        <SettlePaymentModal
          listingId={settleFor}
          open={!!settleFor}
          onOpenChange={(o) => { if (!o) setSettleFor(null); }}
          onPaid={() => { if (onRefresh) onRefresh(); }}
        />

        {showReceipts && (
          <div className="pt-3 border-t" data-testid="buyer-receipts-list">
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-2">
              {fr ? 'Reçus' : 'Receipts'}
            </p>
            {(receipts || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {fr ? 'Aucun reçu pour le moment.' : 'No receipts yet.'}
              </p>
            ) : (
              <div className="space-y-2">
                {receipts.map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2 text-sm p-2.5 bg-slate-50 dark:bg-slate-800 rounded-md" data-testid={`receipt-row-${r.id}`}>
                    <div className="min-w-0">
                      <p className="font-medium truncate">{r.listing_title}</p>
                      <p className="text-xs text-muted-foreground">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                        {r.transaction_id ? ` · ${String(r.transaction_id).slice(0, 18)}…` : ''}
                      </p>
                    </div>
                    <div className="text-right text-xs flex-shrink-0">
                      <p>{fr ? 'Adjudication' : 'Hammer'}: {formatCurrency(r.hammer_price)}</p>
                      <p>{fr ? 'Frais + taxes' : 'Fees + taxes'}: {formatCurrency((r.platform_fee || 0) + (r.taxes || 0) + (r.processing_fee || 0))}</p>
                      <p className="font-bold">{fr ? 'Total' : 'Total charged'}: {formatCurrency(r.total_charged)} CAD</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// ========== iter298 BUG 5 — Deposits ==========
const DepositsCard = ({ deposits }) => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  if (!deposits.length) return null;
  const statusCls = (s) => (
    s === 'refunded' || s === 'released' ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
    : s === 'applied' || s === 'captured' ? 'bg-blue-100 text-blue-800 border-blue-300'
    : 'bg-amber-100 text-amber-800 border-amber-300'
  );
  return (
    <Card className="glassmorphism" data-testid="buyer-deposits-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="h-5 w-5 text-cyan-600" />
          {fr ? 'Mes dépôts' : 'My Deposits'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {deposits.slice(0, 10).map((d) => (
            <div key={d.id || `${d.auction_id}-${d.created_at}`} className="flex items-center justify-between gap-2 p-2.5 border rounded-md text-sm" data-testid={`deposit-row-${d.id || d.auction_id}`}>
              <div className="min-w-0">
                <p className="font-medium truncate">
                  {d.deposit_type === 'storage' ? (fr ? 'Dépôt entreposage' : 'Storage deposit') : (fr ? 'Dépôt d\u2019enchère' : 'Bidding deposit')}
                  {' · '}{formatCurrency(d.amount || 0)}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {d.auction_id ? `${fr ? 'Enchère' : 'Auction'} ${String(d.auction_id).slice(0, 8)}…` : ''}
                  {d.created_at ? ` · ${new Date(d.created_at).toLocaleDateString()}` : ''}
                </p>
              </div>
              <div className="text-right flex-shrink-0">
                <Badge className={`border text-xs ${statusCls(d.status)}`}>{d.status || 'held'}</Badge>
                {(d.status === 'held' || d.status === 'authorized') && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {fr ? 'Remboursé sous 5-7 jours après l\u2019enchère' : 'Refunded 5-7 days after auction'}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

