import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Plus, Trash2, Upload, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CreateMultiItemListing = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    location: '',
    city: '',
    region: '',
    auction_end_date: '',
  });
  const [lots, setLots] = useState([{
    lot_number: 1,
    title: '',
    description: '',
    quantity: 1,
    starting_price: '',
    current_price: '',
    condition: 'good',
    images: []
  }]);

  useEffect(() => {
    if (user && user.account_type !== 'business') {
      toast.error('Only business accounts can create multi-item listings');
      navigate('/dashboard');
    }
    fetchCategories();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setFormData(prev => ({ ...prev, auction_end_date: tomorrow.toISOString().slice(0, 16) }));
  }, [user]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleLotChange = (index, field, value) => {
    const updatedLots = [...lots];
    updatedLots[index][field] = value;
    setLots(updatedLots);
  };

  const addLot = () => {
    setLots([...lots, {
      lot_number: lots.length + 1,
      title: '',
      description: '',
      quantity: 1,
      starting_price: '',
      current_price: '',
      condition: 'good',
      images: []
    }]);
  };

  const removeLot = (index) => {
    const updatedLots = lots.filter((_, i) => i !== index);
    updatedLots.forEach((lot, i) => { lot.lot_number = i + 1; });
    setLots(updatedLots);
  };

  const handleLotImageUpload = (index, e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
      if (file.size > 5000000) {
        toast.error('Image size should be less than 5MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const updatedLots = [...lots];
        updatedLots[index].images = [...updatedLots[index].images, reader.result];
        setLots(updatedLots);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeLotImage = (lotIndex, imageIndex) => {
    const updatedLots = [...lots];
    updatedLots[lotIndex].images = updatedLots[lotIndex].images.filter((_, i) => i !== imageIndex);
    setLots(updatedLots);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const lotsData = lots.map(lot => ({
      ...lot,
      starting_price: parseFloat(lot.starting_price),
      current_price: parseFloat(lot.starting_price),
      quantity: parseInt(lot.quantity)
    }));

    try {
      const payload = {
        ...formData,
        auction_end_date: new Date(formData.auction_end_date).toISOString(),
        lots: lotsData
      };
      const response = await axios.post(`${API}/multi-item-listings`, payload);
      toast.success('Multi-item listing created!');
      navigate(`/multi-item-listing/${response.data.id}`);
    } catch (error) {
      console.error('Failed:', error);
      toast.error(error.response?.data?.detail || 'Failed to create listing');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-5xl mx-auto">
        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle className="text-2xl font-bold">Create Multi-Item Listing</CardTitle>
            <p className="text-muted-foreground">Grouped auction with multiple lots</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-8">
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Auction Details</h3>
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input id="title" name="title" value={formData.title} onChange={handleChange} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea id="description" name="description" value={formData.description} onChange={handleChange} rows={3} required />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="category">Category</Label>
                    <select id="category" name="category" value={formData.category} onChange={handleChange} required className="w-full px-3 py-2 border border-input rounded-md bg-background">
                      <option value="">Select</option>
                      {categories.map(cat => <option key={cat.id} value={cat.name_en}>{cat.name_en}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="auction_end_date">End Date</Label>
                    <Input id="auction_end_date" name="auction_end_date" type="datetime-local" value={formData.auction_end_date} onChange={handleChange} required />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="city">City</Label>
                    <Input id="city" name="city" value={formData.city} onChange={handleChange} required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="region">Region</Label>
                    <Input id="region" name="region" value={formData.region} onChange={handleChange} required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="location">Location</Label>
                    <Input id="location" name="location" value={formData.location} onChange={handleChange} required />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-semibold">Lots ({lots.length})</h3>
                  <Button type="button" onClick={addLot} variant="outline">
                    <Plus className="mr-2 h-4 w-4" /> Add Lot
                  </Button>
                </div>

                {lots.map((lot, index) => (
                  <Card key={index} className="border-2">
                    <CardContent className="pt-6 space-y-4">
                      <div className="flex justify-between">
                        <h4 className="font-semibold">Lot {lot.lot_number}</h4>
                        {lots.length > 1 && (
                          <Button type="button" variant="ghost" size="sm" onClick={() => removeLot(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Title</Label>
                          <Input value={lot.title} onChange={(e) => handleLotChange(index, 'title', e.target.value)} required />
                        </div>
                        <div className="space-y-2">
                          <Label>Quantity</Label>
                          <Input type="number" min="1" value={lot.quantity} onChange={(e) => handleLotChange(index, 'quantity', e.target.value)} required />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label>Description</Label>
                        <Textarea value={lot.description} onChange={(e) => handleLotChange(index, 'description', e.target.value)} rows={2} required />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Starting Price</Label>
                          <Input type="number" step="0.01" value={lot.starting_price} onChange={(e) => handleLotChange(index, 'starting_price', e.target.value)} required />
                        </div>
                        <div className="space-y-2">
                          <Label>Condition</Label>
                          <select value={lot.condition} onChange={(e) => handleLotChange(index, 'condition', e.target.value)} className="w-full px-3 py-2 border border-input rounded-md bg-background">
                            <option value="new">New</option>
                            <option value="like_new">Like New</option>
                            <option value="good">Good</option>
                            <option value="fair">Fair</option>
                            <option value="poor">Poor</option>
                          </select>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label>Images</Label>
                        <input type="file" accept="image/*" multiple onChange={(e) => handleLotImageUpload(index, e)} className="hidden" id={`lot-image-${index}`} />
                        <Button type="button" variant="outline" onClick={() => document.getElementById(`lot-image-${index}`).click()} className="w-full">
                          <Upload className="mr-2 h-4 w-4" /> Upload
                        </Button>
                        {lot.images.length > 0 && (
                          <div className="grid grid-cols-3 gap-2">
                            {lot.images.map((img, imgIdx) => (
                              <div key={imgIdx} className="relative aspect-square rounded-lg overflow-hidden bg-gray-100">
                                <img src={img} alt="" className="w-full h-full object-cover" />
                                <button type="button" onClick={() => removeLotImage(index, imgIdx)} className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 text-xs">×</button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Button type="submit" className="w-full gradient-button text-white border-0" disabled={loading}>
                {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating...</> : 'Create'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default CreateMultiItemListing;
