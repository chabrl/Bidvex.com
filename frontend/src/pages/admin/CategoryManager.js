import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { FolderOpen, Plus, Edit2, Trash2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CategoryManager = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name_en: '',
    name_fr: '',
    icon: '📦',
    order: 0
  });

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      toast.error('Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    try {
      if (editingId) {
        await axios.put(`${API}/admin/categories/${editingId}`, formData);
        toast.success('Category updated');
      } else {
        await axios.post(`${API}/admin/categories`, formData);
        toast.success('Category created');
      }
      resetForm();
      fetchCategories();
    } catch (error) {
      toast.error('Failed to save category');
    }
  };

  const handleEdit = (category) => {
    setEditingId(category.id);
    setFormData({
      name_en: category.name_en,
      name_fr: category.name_fr,
      icon: category.icon || '📦',
      order: category.order || 0
    });
    setShowCreate(true);
  };

  const handleDelete = async (categoryId) => {
    if (window.confirm('Delete this category? This will affect all listings in this category.')) {
      try {
        await axios.delete(`${API}/admin/categories/${categoryId}`);
        toast.success('Category deleted');
        fetchCategories();
      } catch (error) {
        toast.error('Failed to delete category');
      }
    }
  };

  const resetForm = () => {
    setFormData({ name_en: '', name_fr: '', icon: '📦', order: 0 });
    setEditingId(null);
    setShowCreate(false);
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><FolderOpen className="h-6 w-6" />Category Management</h2>
          <p className="text-muted-foreground">Manage listing categories</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gradient-button text-white border-0">
          <Plus className="h-4 w-4 mr-2" />{editingId ? 'Cancel Edit' : 'Add Category'}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-2 border-primary">
          <CardHeader><CardTitle>{editingId ? 'Edit Category' : 'Create New Category'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Name (English)</label>
                <Input value={formData.name_en} onChange={(e) => setFormData({...formData, name_en: e.target.value})} placeholder="Electronics" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Name (French)</label>
                <Input value={formData.name_fr} onChange={(e) => setFormData({...formData, name_fr: e.target.value})} placeholder="Électronique" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Icon (Emoji)</label>
                <Input value={formData.icon} onChange={(e) => setFormData({...formData, icon: e.target.value})} placeholder="📦" maxLength={2} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Display Order</label>
                <Input type="number" value={formData.order} onChange={(e) => setFormData({...formData, order: parseInt(e.target.value)})} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSubmit} className="gradient-button text-white border-0">{editingId ? 'Update' : 'Create'}</Button>
              <Button variant="outline" onClick={resetForm}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Categories ({categories.length})</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {categories.map(category => (
              <div key={category.id} className="flex justify-between items-center p-4 border rounded-lg hover:bg-accent transition-colors">
                <div className="flex items-center gap-4">
                  <span className="text-3xl">{category.icon || '📦'}</span>
                  <div>
                    <p className="font-semibold">{category.name_en} / {category.name_fr}</p>
                    <p className="text-xs text-muted-foreground">Order: {category.order || 0}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleEdit(category)}><Edit2 className="h-4 w-4" /></Button>
                  <Button size="sm" variant="destructive" onClick={() => handleDelete(category.id)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CategoryManager;