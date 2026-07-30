import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { FolderOpen, Plus, Edit2, Trash2, ChevronRight } from 'lucide-react';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const CategoryManager = () => {
  const { token } = useAuth();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name_en: '', name_fr: '', icon: '', order: 0, parent_id: null
  });

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => { fetchCategories(); }, []);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/admin/categories`, { headers });
      const data = Array.isArray(response.data) ? response.data : response.data.categories || [];
      setCategories(data);
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  const topLevel = categories.filter(c => !c.parent_id);
  const getChildren = (parentId) => categories.filter(c => c.parent_id === parentId);

  const handleSubmit = async () => {
    if (!formData.name_en.trim()) { toast.error('English name is required'); return; }
    try {
      const payload = { ...formData, parent_id: formData.parent_id || null };
      if (editingId) {
        await axios.put(`${API}/admin/categories/${editingId}`, payload, { headers });
        toast.success('Category updated');
      } else {
        await axios.post(`${API}/admin/categories`, payload, { headers });
        toast.success('Category created');
      }
      resetForm();
      fetchCategories();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to save category');
    }
  };

  const handleEdit = (category) => {
    setEditingId(category.id);
    setFormData({
      name_en: category.name_en || '', name_fr: category.name_fr || '',
      icon: category.icon || '', order: category.order || 0,
      parent_id: category.parent_id || null
    });
    setShowCreate(true);
  };

  const handleDelete = async (categoryId) => {
    const children = getChildren(categoryId);
    if (children.length > 0 && !window.confirm('This category has subcategories. Delete all?')) return;
    if (!window.confirm('Delete this category? This will affect all listings using it.')) return;
    try {
      await axios.delete(`${API}/admin/categories/${categoryId}`, { headers });
      toast.success('Category deleted');
      fetchCategories();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to delete category');
    }
  };

  const resetForm = () => {
    setFormData({ name_en: '', name_fr: '', icon: '', order: 0, parent_id: null });
    setEditingId(null);
    setShowCreate(false);
  };

  if (loading) return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><FolderOpen className="h-6 w-6" />Category Management</h2>
          <p className="text-muted-foreground">{topLevel.length} categories, {categories.length - topLevel.length} subcategories</p>
        </div>
        <Button onClick={() => { showCreate ? resetForm() : setShowCreate(true); }} className="gradient-button text-white border-0">
          <Plus className="h-4 w-4 mr-2" />{editingId ? 'Cancel Edit' : 'Add Category'}
        </Button>
      </div>

      {showCreate && (
        <Card className="border-2 border-primary">
          <CardHeader><CardTitle>{editingId ? 'Edit Category' : 'Create New Category'}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Name (English) *</label>
                <Input data-testid="category-name-en" value={formData.name_en} onChange={(e) => setFormData({...formData, name_en: e.target.value})} placeholder="Electronics" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Name (French)</label>
                <Input data-testid="category-name-fr" value={formData.name_fr} onChange={(e) => setFormData({...formData, name_fr: e.target.value})} placeholder="Électronique" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Icon (Emoji)</label>
                <Input value={formData.icon} onChange={(e) => setFormData({...formData, icon: e.target.value})} placeholder="📦" maxLength={4} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Display Order</label>
                <Input type="number" value={formData.order} onChange={(e) => setFormData({...formData, order: parseInt(e.target.value) || 0})} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Parent Category</label>
                <select
                  data-testid="category-parent-select"
                  className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={formData.parent_id || ''}
                  onChange={(e) => setFormData({...formData, parent_id: e.target.value || null})}
                >
                  <option value="">— Top Level —</option>
                  {topLevel.filter(c => c.id !== editingId).map(c => (
                    <option key={c.id} value={c.id}>{c.icon} {c.name_en}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <Button data-testid="category-submit-btn" onClick={handleSubmit} className="gradient-button text-white border-0">{editingId ? 'Update' : 'Create'}</Button>
              <Button variant="outline" onClick={resetForm}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Categories ({categories.length})</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {topLevel.map(category => (
              <div key={category.id}>
                <div className="flex justify-between items-center p-4 border rounded-lg hover:bg-accent transition-colors">
                  <div className="flex items-center gap-4">
                    <span className="text-3xl">{category.icon || '📦'}</span>
                    <div>
                      <p className="font-semibold">{category.name_en}{category.name_fr ? ` / ${category.name_fr}` : ''}</p>
                      <p className="text-xs text-muted-foreground">Order: {category.order || 0} | {getChildren(category.id).length} subcategories</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => handleEdit(category)} data-testid={`edit-category-${category.id}`}><Edit2 className="h-4 w-4" /></Button>
                    <Button size="sm" variant="destructive" onClick={() => handleDelete(category.id)} data-testid={`delete-category-${category.id}`}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </div>
                {getChildren(category.id).map(sub => (
                  <div key={sub.id} className="flex justify-between items-center p-3 pl-12 border-l-4 border-primary/20 ml-6 mt-1 rounded-r-lg hover:bg-accent/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xl">{sub.icon || '📂'}</span>
                      <div>
                        <p className="font-medium text-sm">{sub.name_en}{sub.name_fr ? ` / ${sub.name_fr}` : ''}</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => handleEdit(sub)}><Edit2 className="h-3.5 w-3.5" /></Button>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => handleDelete(sub.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CategoryManager;
