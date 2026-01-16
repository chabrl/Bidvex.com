import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { extractErrorMessage } from '../utils/errorHandler';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Loader2, Upload } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CreateListingPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    condition: 'good',
    starting_price: '',
    buy_now_price: '',
    images: [],
    location: '',
    city: '',
    region: '',
    auction_end_date: '',
  });

  // Shipping & Visit Options
  const [shippingInfo, setShippingInfo] = useState({
    available: false,
    methods: [],
    rates: {},
    delivery_time: ''
  });

  const [visitAvailability, setVisitAvailability] = useState({
    offered: false,
    dates: '',
    instructions: ''
  });

  useEffect(() => {
    fetchCategories();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setFormData(prev => ({
      ...prev,
      auction_end_date: tomorrow.toISOString().slice(0, 16)
    }));
  }, []);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleImageUpload = (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        setFormData(prev => ({
          ...prev,
          images: [...prev.images, reader.result]
        }));
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (index) => {
    setFormData({
      ...formData,
      images: formData.images.filter((_, i) => i !== index)
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        ...formData,
        starting_price: parseFloat(formData.starting_price),
        buy_now_price: formData.buy_now_price ? parseFloat(formData.buy_now_price) : null,
        auction_end_date: new Date(formData.auction_end_date).toISOString(),
        shipping_info: shippingInfo.available ? shippingInfo : null,
        visit_availability: visitAvailability.offered ? visitAvailability : null,
      };

      const response = await axios.post(`${API}/listings`, payload);
      toast.success('Listing created successfully!');
      navigate(`/listing/${response.data.id}`);
    } catch (error) {
      console.error('Failed to create listing:', error);
      toast.error(error.response?.data?.detail || 'Failed to create listing');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen py-8 px-4" data-testid="create-listing-page">
      <div className="max-w-3xl mx-auto">
        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle className="text-2xl font-bold">Create New Listing</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="title">Title *</Label>
                <Input
                  id="title"
                  name="title"
                  value={formData.title}
                  onChange={handleChange}
                  required
                  data-testid="title-input"
                  placeholder="Enter a descriptive title"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description *</Label>
                <Textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  required
                  rows={4}
                  data-testid="description-input"
                  placeholder="Describe your item in detail"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Category *</Label>
                  <select
                    id="category"
                    name="category"
                    value={formData.category}
                    onChange={handleChange}
                    required
                    className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    data-testid="category-select"
                  >
                    <option value="">Select category</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.name_en}>
                        {cat.name_en}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="condition">Condition *</Label>
                  <select
                    id="condition"
                    name="condition"
                    value={formData.condition}
                    onChange={handleChange}
                    required
                    className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    data-testid="condition-select"
                  >
                    <option value="new">New</option>
                    <option value="like_new">Like New</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="poor">Poor</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="starting_price">Starting Price ($) *</Label>
                  <Input
                    id="starting_price"
                    name="starting_price"
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={formData.starting_price}
                    onChange={handleChange}
                    required
                    data-testid="starting-price-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="buy_now_price">Buy Now Price ($)</Label>
                  <Input
                    id="buy_now_price"
                    name="buy_now_price"
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={formData.buy_now_price}
                    onChange={handleChange}
                    data-testid="buy-now-price-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City *</Label>
                  <Input
                    id="city"
                    name="city"
                    value={formData.city}
                    onChange={handleChange}
                    required
                    data-testid="city-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="region">Region/State *</Label>
                  <Input
                    id="region"
                    name="region"
                    value={formData.region}
                    onChange={handleChange}
                    required
                    data-testid="region-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="location">Location *</Label>
                  <Input
                    id="location"
                    name="location"
                    value={formData.location}
                    onChange={handleChange}
                    required
                    data-testid="location-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auction_end_date">Auction End Date *</Label>
                <Input
                  id="auction_end_date"
                  name="auction_end_date"
                  type="datetime-local"
                  value={formData.auction_end_date}
                  onChange={handleChange}
                  required
                  data-testid="end-date-input"
                />
              </div>

              <div className="space-y-2">
                <Label>Images</Label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageUpload}
                  className="hidden"
                  id="image-upload"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => document.getElementById('image-upload').click()}
                  className="w-full"
                  data-testid="add-image-btn"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  Upload Images from Device
                </Button>
                {formData.images.length > 0 && (
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {formData.images.map((img, index) => (
                      <div key={index} className="relative aspect-square rounded-lg overflow-hidden bg-gray-100">
                        <img src={img} alt={`Preview ${index + 1}`} className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() => removeImage(index)}
                          className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Shipping Options Section */}
              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="text-lg">🚚 Shipping Options</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="shipping-available"
                      checked={shippingInfo.available}
                      onChange={(e) => setShippingInfo(prev => ({ ...prev, available: e.target.checked }))}
                      className="w-4 h-4"
                    />
                    <Label htmlFor="shipping-available">Offer Shipping?</Label>
                  </div>

                  {shippingInfo.available && (
                    <div className="space-y-4 ml-6 p-4 border rounded-lg bg-muted/20">
                      <div>
                        <Label>Shipping Methods</Label>
                        <div className="space-y-2 mt-2">
                          {['local_pickup', 'standard', 'express'].map(method => (
                            <div key={method} className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                id={`shipping-${method}`}
                                checked={shippingInfo.methods.includes(method)}
                                onChange={(e) => {
                                  setShippingInfo(prev => ({
                                    ...prev,
                                    methods: e.target.checked
                                      ? [...prev.methods, method]
                                      : prev.methods.filter(m => m !== method)
                                  }));
                                }}
                                className="w-4 h-4"
                              />
                              <Label htmlFor={`shipping-${method}`} className="capitalize">
                                {method.replace('_', ' ')}
                              </Label>
                              {shippingInfo.methods.includes(method) && (
                                <Input
                                  type="number"
                                  placeholder="Rate ($)"
                                  value={shippingInfo.rates[method] || ''}
                                  onChange={(e) => setShippingInfo(prev => ({
                                    ...prev,
                                    rates: { ...prev.rates, [method]: e.target.value }
                                  }))}
                                  className="w-24"
                                />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <Label>Estimated Delivery Time</Label>
                        <Input
                          placeholder="e.g., 3-5 business days"
                          value={shippingInfo.delivery_time}
                          onChange={(e) => setShippingInfo(prev => ({ ...prev, delivery_time: e.target.value }))}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Visit Availability Section */}
              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="text-lg">🏠 Visit Before Purchase</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="visit-offered"
                      checked={visitAvailability.offered}
                      onChange={(e) => setVisitAvailability(prev => ({ ...prev, offered: e.target.checked }))}
                      className="w-4 h-4"
                    />
                    <Label htmlFor="visit-offered">Allow buyers to schedule a visit?</Label>
                  </div>

                  {visitAvailability.offered && (
                    <div className="space-y-4 ml-6 p-4 border rounded-lg bg-green-50 dark:bg-green-900/10">
                      <div>
                        <Label>Available Dates</Label>
                        <Input
                          placeholder="e.g., Nov 15-20, 2025"
                          value={visitAvailability.dates}
                          onChange={(e) => setVisitAvailability(prev => ({ ...prev, dates: e.target.value }))}
                        />
                      </div>

                      <div>
                        <Label>Instructions</Label>
                        <Textarea
                          placeholder="Provide instructions for scheduling (e.g., contact info, time slots)"
                          value={visitAvailability.instructions}
                          onChange={(e) => setVisitAvailability(prev => ({ ...prev, instructions: e.target.value }))}
                          rows={3}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Button
                type="submit"
                className="w-full gradient-button text-white border-0"
                disabled={loading}
                data-testid="submit-listing-btn"
              >
                {loading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating...</>
                ) : (
                  'Create Listing'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default CreateListingPage;
