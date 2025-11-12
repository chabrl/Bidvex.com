import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Mail, Phone, MapPin, Star, Package, Calendar, 
  MessageCircle, ArrowLeft, Building, User
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SellerProfilePage = () => {
  const { t } = useTranslation();
  const { sellerId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [seller, setSeller] = useState(null);
  const [listings, setListings] = useState({ single_listings: [], multi_listings: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSellerProfile();
    fetchSellerListings();
  }, [sellerId]);

  const fetchSellerProfile = async () => {
    try {
      const headers = {};
      if (user) {
        headers.Authorization = `Bearer ${localStorage.getItem('token')}`;
      }
      const response = await axios.get(`${API}/sellers/${sellerId}`, { headers });
      setSeller(response.data);
    } catch (error) {
      console.error('Failed to fetch seller profile:', error);
      toast.error('Failed to load seller profile');
    } finally {
      setLoading(false);
    }
  };

  const fetchSellerListings = async () => {
    try {
      const response = await axios.get(`${API}/sellers/${sellerId}/listings`);
      setListings(response.data);
    } catch (error) {
      console.error('Failed to fetch seller listings:', error);
    }
  };

  const renderRating = (rating) => {
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      stars.push(
        <Star 
          key={i} 
          className={`h-5 w-5 ${i <= rating ? 'fill-amber-500 text-amber-500' : 'text-gray-300'}`}
        />
      );
    }
    return <div className="flex gap-1">{stars}</div>;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  if (!seller) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">Seller not found</p>
          <Button onClick={() => navigate('/')} className="mt-4">Go Home</Button>
        </Card>
      </div>
    );
  }

  const totalListings = listings.single_listings.length + listings.multi_listings.length;

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Back Button */}
        <Button 
          variant="ghost" 
          onClick={() => navigate(-1)}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          {t('common.back', 'Back')}
        </Button>

        {/* Seller Profile Card */}
        <Card>
          <CardContent className="p-8">
            <div className="flex flex-col md:flex-row gap-6">
              {/* Avatar */}
              <div className="flex-shrink-0">
                {seller.picture ? (
                  <img 
                    src={seller.picture} 
                    alt={seller.name}
                    className="w-32 h-32 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-32 h-32 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                    <User className="h-16 w-16 text-white" />
                  </div>
                )}
              </div>

              {/* Profile Info */}
              <div className="flex-1 space-y-4">
                <div>
                  <div className="flex items-center gap-3 flex-wrap mb-2">
                    <h1 className="text-3xl font-bold">{seller.name}</h1>
                    {seller.subscription_tier === 'vip' && (
                      <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-white">
                        ⭐ VIP Seller
                      </Badge>
                    )}
                    {seller.subscription_tier === 'premium' && (
                      <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white">
                        ✨ Premium Seller
                      </Badge>
                    )}
                  </div>
                  
                  {seller.company_name && (
                    <div className="flex items-center gap-2 text-muted-foreground mb-2">
                      <Building className="h-4 w-4" />
                      <span>{seller.company_name}</span>
                    </div>
                  )}
                  
                  {/* Rating */}
                  {seller.average_rating > 0 && (
                    <div className="flex items-center gap-3 mt-3">
                      {renderRating(seller.average_rating)}
                      <span className="text-lg font-semibold">{seller.average_rating.toFixed(1)}</span>
                      <span className="text-sm text-muted-foreground">
                        ({seller.total_ratings} {seller.total_ratings === 1 ? 'rating' : 'ratings'})
                      </span>
                    </div>
                  )}
                </div>

                {/* Bio */}
                {seller.bio && (
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{seller.bio}</p>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-4 border-t">
                  <div className="text-center p-3 bg-primary/5 rounded-lg">
                    <Package className="h-5 w-5 mx-auto mb-2 text-primary" />
                    <p className="text-2xl font-bold">{seller.total_active_listings}</p>
                    <p className="text-xs text-muted-foreground">Active Listings</p>
                  </div>
                  <div className="text-center p-3 bg-primary/5 rounded-lg">
                    <Star className="h-5 w-5 mx-auto mb-2 text-amber-500" />
                    <p className="text-2xl font-bold">{seller.average_rating.toFixed(1)}</p>
                    <p className="text-xs text-muted-foreground">Average Rating</p>
                  </div>
                  <div className="text-center p-3 bg-primary/5 rounded-lg">
                    <Calendar className="h-5 w-5 mx-auto mb-2 text-primary" />
                    <p className="text-2xl font-bold">
                      {new Date(seller.member_since).getFullYear()}
                    </p>
                    <p className="text-xs text-muted-foreground">Member Since</p>
                  </div>
                </div>

                {/* Contact Info (Only for authenticated users) */}
                {user && (seller.email || seller.phone || seller.address) && (
                  <div className="space-y-3 pt-4 border-t">
                    <h3 className="font-semibold text-lg">Contact Information</h3>
                    {seller.email && (
                      <div className="flex items-center gap-3 text-sm">
                        <Mail className="h-4 w-4 text-muted-foreground" />
                        <a href={`mailto:${seller.email}`} className="text-primary hover:underline">
                          {seller.email}
                        </a>
                      </div>
                    )}
                    {seller.phone && (
                      <div className="flex items-center gap-3 text-sm">
                        <Phone className="h-4 w-4 text-muted-foreground" />
                        <a href={`tel:${seller.phone}`} className="hover:underline">
                          {seller.phone}
                        </a>
                      </div>
                    )}
                    {seller.address && (
                      <div className="flex items-start gap-3 text-sm">
                        <MapPin className="h-4 w-4 text-muted-foreground mt-1" />
                        <span>{seller.address}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Contact Seller Button */}
                {user && user.id !== seller.id && (
                  <Button className="w-full md:w-auto mt-4" onClick={() => navigate(`/messages`)}>
                    <MessageCircle className="h-4 w-4 mr-2" />
                    Contact Seller
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Active Listings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Active Listings ({totalListings})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {totalListings === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No active listings at the moment</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Multi-Lot Auctions */}
                {listings.multi_listings.map((listing) => (
                  <Card 
                    key={listing.id}
                    className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => navigate(`/lots/${listing.id}`)}
                  >
                    <div className="aspect-video bg-gray-100 relative">
                      {listing.lots && listing.lots[0]?.images?.[0] ? (
                        <img 
                          src={listing.lots[0].images[0]} 
                          alt={listing.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-6xl">🎯</div>
                      )}
                      <Badge className="absolute top-2 left-2 bg-purple-500">
                        Multi-Lot
                      </Badge>
                    </div>
                    <CardContent className="p-4">
                      <h3 className="font-semibold line-clamp-2 mb-2">{listing.title}</h3>
                      <p className="text-sm text-muted-foreground">{listing.total_lots} lots</p>
                    </CardContent>
                  </Card>
                ))}

                {/* Single Listings */}
                {listings.single_listings.map((listing) => (
                  <Card 
                    key={listing.id}
                    className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => navigate(`/listing/${listing.id}`)}
                  >
                    <div className="aspect-video bg-gray-100">
                      {listing.images && listing.images[0] ? (
                        <img 
                          src={listing.images[0]} 
                          alt={listing.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
                      )}
                    </div>
                    <CardContent className="p-4">
                      <h3 className="font-semibold line-clamp-2 mb-2">{listing.title}</h3>
                      <p className="text-lg font-bold text-primary">
                        ${listing.current_price.toFixed(2)}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default SellerProfilePage;
