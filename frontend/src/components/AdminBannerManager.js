/**
 * BidVex Admin Banner Management Component
 * Allows admins to manage homepage promotional banners
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import {
  Image as ImageIcon, Link as LinkIcon, Clock, Plus, Trash2, Edit2,
  Eye, EyeOff, Upload, Save, Loader2, RefreshCw
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminBannerManager = () => {
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingBanner, setEditingBanner] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const [newBanner, setNewBanner] = useState({
    title: '',
    image_url: '',
    cta_text: '',
    cta_url: '',
    is_active: true,
    start_date: '',
    end_date: '',
    priority: 0
  });

  const fetchBanners = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/admin/banners`);
      setBanners(response.data.banners || []);
    } catch (error) {
      console.error('Failed to fetch banners:', error);
      toast.error('Failed to load banners');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBanners();
  }, [fetchBanners]);

  const handleSaveBanner = async (banner) => {
    try {
      setSaving(true);
      if (banner.id) {
        await axios.put(`${API}/admin/banners/${banner.id}`, banner);
        toast.success('Banner updated successfully!');
      } else {
        await axios.post(`${API}/admin/banners`, banner);
        toast.success('Banner created successfully!');
      }
      fetchBanners();
      setEditingBanner(null);
      setShowAddForm(false);
      resetNewBanner();
    } catch (error) {
      console.error('Failed to save banner:', error);
      toast.error('Failed to save banner');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBanner = async (bannerId) => {
    if (!window.confirm('Are you sure you want to delete this banner?')) return;
    
    try {
      await axios.delete(`${API}/admin/banners/${bannerId}`);
      toast.success('Banner deleted successfully!');
      fetchBanners();
    } catch (error) {
      console.error('Failed to delete banner:', error);
      toast.error('Failed to delete banner');
    }
  };

  const handleToggleActive = async (banner) => {
    try {
      await axios.put(`${API}/admin/banners/${banner.id}`, {
        ...banner,
        is_active: !banner.is_active
      });
      toast.success(`Banner ${!banner.is_active ? 'activated' : 'deactivated'}`);
      fetchBanners();
    } catch (error) {
      console.error('Failed to toggle banner:', error);
      toast.error('Failed to update banner status');
    }
  };

  const resetNewBanner = () => {
    setNewBanner({
      title: '',
      image_url: '',
      cta_text: '',
      cta_url: '',
      is_active: true,
      start_date: '',
      end_date: '',
      priority: 0
    });
  };

  const handleImageUpload = async (file, setBannerFn) => {
    const reader = new FileReader();
    reader.onload = () => {
      setBannerFn(prev => ({ ...prev, image_url: reader.result }));
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
            Banner Management
          </h2>
          <p className="text-slate-500 dark:text-slate-400">
            Manage homepage promotional banners
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={fetchBanners} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={() => setShowAddForm(true)}
            className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white border-0"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Banner
          </Button>
        </div>
      </div>

      {/* Info Card */}
      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardContent className="p-4">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>📐 Recommended Size:</strong> 1920x600px for optimal display.
            Banners are displayed on the homepage hero section.
          </p>
        </CardContent>
      </Card>

      {/* Add Banner Form */}
      {showAddForm && (
        <Card className="border-2 border-[#06B6D4]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-[#06B6D4]" />
              Add New Banner
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BannerForm
              banner={newBanner}
              setBanner={setNewBanner}
              onSave={() => handleSaveBanner(newBanner)}
              onCancel={() => {
                setShowAddForm(false);
                resetNewBanner();
              }}
              saving={saving}
              onImageUpload={(file) => handleImageUpload(file, setNewBanner)}
            />
          </CardContent>
        </Card>
      )}

      {/* Banner List */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-[#06B6D4]" />
          </div>
        ) : banners.length === 0 ? (
          <Card className="py-12">
            <CardContent className="text-center">
              <ImageIcon className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
              <p className="text-slate-500 dark:text-slate-400">No banners configured</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => setShowAddForm(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Your First Banner
              </Button>
            </CardContent>
          </Card>
        ) : (
          banners.map((banner) => (
            <Card key={banner.id} className={`transition-all ${!banner.is_active ? 'opacity-60' : ''}`}>
              <CardContent className="p-4">
                {editingBanner?.id === banner.id ? (
                  <BannerForm
                    banner={editingBanner}
                    setBanner={setEditingBanner}
                    onSave={() => handleSaveBanner(editingBanner)}
                    onCancel={() => setEditingBanner(null)}
                    saving={saving}
                    onImageUpload={(file) => handleImageUpload(file, setEditingBanner)}
                  />
                ) : (
                  <div className="flex items-start gap-4">
                    {/* Thumbnail */}
                    <div className="w-48 h-28 rounded-lg overflow-hidden bg-slate-100 dark:bg-slate-800 flex-shrink-0">
                      {banner.image_url ? (
                        <img
                          src={banner.image_url}
                          alt={banner.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <ImageIcon className="h-8 w-8 text-slate-400" />
                        </div>
                      )}
                    </div>

                    {/* Details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-slate-900 dark:text-white truncate">
                          {banner.title || 'Untitled Banner'}
                        </h3>
                        {banner.is_active ? (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                            Active
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500">
                            Inactive
                          </span>
                        )}
                      </div>
                      
                      {banner.cta_text && (
                        <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1">
                          <LinkIcon className="h-3 w-3" />
                          {banner.cta_text} → {banner.cta_url || 'No URL'}
                        </p>
                      )}

                      {(banner.start_date || banner.end_date) && (
                        <p className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1 mt-1">
                          <Clock className="h-3 w-3" />
                          {banner.start_date && `From: ${new Date(banner.start_date).toLocaleDateString()}`}
                          {banner.start_date && banner.end_date && ' - '}
                          {banner.end_date && `Until: ${new Date(banner.end_date).toLocaleDateString()}`}
                        </p>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleActive(banner)}
                        title={banner.is_active ? 'Deactivate' : 'Activate'}
                      >
                        {banner.is_active ? (
                          <Eye className="h-4 w-4 text-green-500" />
                        ) : (
                          <EyeOff className="h-4 w-4 text-slate-400" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setEditingBanner({ ...banner })}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteBanner(banner.id)}
                        className="text-red-500 hover:text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

// Banner Form Component
const BannerForm = ({ banner, setBanner, onSave, onCancel, saving, onImageUpload }) => {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="title">Banner Title</Label>
          <Input
            id="title"
            value={banner.title}
            onChange={(e) => setBanner({ ...banner, title: e.target.value })}
            placeholder="Anniversary Sale Banner"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="priority">Priority (Higher = First)</Label>
          <Input
            id="priority"
            type="number"
            value={banner.priority}
            onChange={(e) => setBanner({ ...banner, priority: parseInt(e.target.value) || 0 })}
            placeholder="0"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Banner Image</Label>
        <div className="flex items-center gap-4">
          <div className="w-48 h-28 rounded-lg overflow-hidden bg-slate-100 dark:bg-slate-800 border-2 border-dashed border-slate-300 dark:border-slate-600">
            {banner.image_url ? (
              <img
                src={banner.image_url}
                alt="Preview"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
                <Upload className="h-6 w-6 mb-1" />
                <span className="text-xs">1920x600px</span>
              </div>
            )}
          </div>
          <div className="flex-1 space-y-2">
            <Input
              type="file"
              accept="image/*"
              onChange={(e) => e.target.files[0] && onImageUpload(e.target.files[0])}
              className="text-sm"
            />
            <p className="text-xs text-slate-500">Or paste an image URL:</p>
            <Input
              value={banner.image_url?.startsWith('data:') ? '' : banner.image_url}
              onChange={(e) => setBanner({ ...banner, image_url: e.target.value })}
              placeholder="https://example.com/banner.jpg"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="cta_text">Button Text (CTA)</Label>
          <Input
            id="cta_text"
            value={banner.cta_text}
            onChange={(e) => setBanner({ ...banner, cta_text: e.target.value })}
            placeholder="Shop Now"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="cta_url">Button Link (URL)</Label>
          <Input
            id="cta_url"
            value={banner.cta_url}
            onChange={(e) => setBanner({ ...banner, cta_url: e.target.value })}
            placeholder="/marketplace"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="start_date">Start Date (Optional)</Label>
          <Input
            id="start_date"
            type="datetime-local"
            value={banner.start_date}
            onChange={(e) => setBanner({ ...banner, start_date: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="end_date">End Date (Optional)</Label>
          <Input
            id="end_date"
            type="datetime-local"
            value={banner.end_date}
            onChange={(e) => setBanner({ ...banner, end_date: e.target.value })}
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Switch
          checked={banner.is_active}
          onCheckedChange={(checked) => setBanner({ ...banner, is_active: checked })}
        />
        <Label>Active (visible on homepage)</Label>
      </div>

      <div className="flex items-center gap-3 pt-4 border-t">
        <Button
          onClick={onSave}
          disabled={saving}
          className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white border-0"
        >
          {saving ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving...</>
          ) : (
            <><Save className="h-4 w-4 mr-2" /> Save Banner</>
          )}
        </Button>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
};

export default AdminBannerManager;
