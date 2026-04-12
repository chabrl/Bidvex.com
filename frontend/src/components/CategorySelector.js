import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useCategoryTree } from '../hooks/useCategoryTree';
import { Label } from '../components/ui/label';
import { ChevronRight, Loader2 } from 'lucide-react';

/**
 * Two-step category selector for seller flows.
 * Step 1: Select parent category
 * Step 2: Select subcategory (only shown if parent has children)
 *
 * Props:
 *   value        — current category name_en string (e.g. "Machining & Welding")
 *   onChange      — callback(name_en) when category changes
 *   label         — optional label override
 *   required      — HTML required attribute
 *   filterVehicles — if true, hides vehicle categories for non-partner users
 *   userRole      — 'admin' | 'partner' | 'personal' etc.
 */
const CategorySelector = ({
  value = '',
  onChange,
  label,
  required = false,
  filterVehicles = true,
  userRole = '',
}) => {
  const { t } = useTranslation();
  const { tree, isLoading, getName, findByNameEn, getParent } = useCategoryTree();

  const [selectedParentId, setSelectedParentId] = useState('');
  const [selectedChildName, setSelectedChildName] = useState('');

  // Sync from external value (e.g. edit mode)
  useEffect(() => {
    if (!value || tree.length === 0) return;
    // Check if value is a child
    const parentNode = getParent(value);
    if (parentNode) {
      setSelectedParentId(parentNode.id);
      setSelectedChildName(value);
    } else {
      // Value is a root category
      const root = tree.find(r => r.nameEn === value);
      if (root) {
        setSelectedParentId(root.id);
        setSelectedChildName(root.children.length === 0 ? value : '');
      }
    }
  }, [value, tree]);

  const isPartnerOrAdmin = userRole === 'partner' || userRole === 'admin';

  // Filter tree for vehicle restriction
  const filteredTree = tree.filter(parent => {
    if (!filterVehicles) return true;
    const isVehicle = parent.nameEn?.toLowerCase() === 'vehicle' || parent.nameEn?.toLowerCase() === 'vehicles';
    return !isVehicle || isPartnerOrAdmin;
  });

  const selectedParent = tree.find(p => p.id === selectedParentId);
  const hasChildren = selectedParent?.children?.length > 0;

  // Breadcrumb
  const breadcrumb = (() => {
    if (!selectedParent) return null;
    const parentName = getName(selectedParent);
    if (selectedChildName && hasChildren) {
      const childNode = selectedParent.children.find(c => c.nameEn === selectedChildName);
      const childName = childNode ? getName(childNode) : selectedChildName;
      return (
        <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 mt-1.5 mb-0.5" data-testid="category-breadcrumb">
          <span className="text-sm">{selectedParent.icon}</span>
          <span className="font-medium text-slate-600 dark:text-slate-300">{parentName}</span>
          <ChevronRight className="w-3 h-3" />
          <span className="text-sm">{childNode?.icon}</span>
          <span className="font-medium text-slate-600 dark:text-slate-300">{childName}</span>
        </div>
      );
    }
    if (selectedParent && !hasChildren) {
      return (
        <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 mt-1.5 mb-0.5" data-testid="category-breadcrumb">
          <span className="text-sm">{selectedParent.icon}</span>
          <span className="font-medium text-slate-600 dark:text-slate-300">{parentName}</span>
        </div>
      );
    }
    return null;
  })();

  const handleParentChange = (e) => {
    const parentId = e.target.value;
    setSelectedParentId(parentId);
    setSelectedChildName('');

    const parent = tree.find(p => p.id === parentId);
    if (parent && parent.children.length === 0) {
      // Leaf parent — auto-select it as the category
      onChange(parent.nameEn);
    } else {
      // Has children — wait for subcategory selection; clear value
      onChange('');
    }
  };

  const handleChildChange = (e) => {
    const childNameEn = e.target.value;
    setSelectedChildName(childNameEn);
    onChange(childNameEn);
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Label>{label || t('createListing.category', 'Category')} {required && '*'}</Label>
        <div className="flex items-center gap-2 h-10 px-3 border border-input rounded-md bg-background text-sm text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin" /> {t('common.loading', 'Loading...')}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="category-selector">
      <Label>{label || t('createListing.category', 'Category')} {required && '*'}</Label>

      {/* Breadcrumb */}
      {breadcrumb}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Step 1: Parent Category */}
        <div>
          <select
            value={selectedParentId}
            onChange={handleParentChange}
            className="w-full px-3 py-2 border border-input rounded-md bg-background text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
            data-testid="category-parent-select"
            required={required}
          >
            <option value="">{t('createListing.selectCategory', 'Select category...')}</option>
            {filteredTree.map(parent => (
              <option key={parent.id} value={parent.id}>
                {parent.icon} {getName(parent)}
              </option>
            ))}
          </select>
        </div>

        {/* Step 2: Subcategory (only if parent has children) */}
        {selectedParentId && hasChildren && (
          <div>
            <select
              value={selectedChildName}
              onChange={handleChildChange}
              className="w-full px-3 py-2 border border-input rounded-md bg-background text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              data-testid="category-child-select"
              required={required}
            >
              <option value="">{t('createListing.selectSubcategory', 'Select subcategory...')}</option>
              {selectedParent.children.map(child => (
                <option key={child.id} value={child.nameEn}>
                  {child.icon} {getName(child)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Hidden input for form validation if using native form submit */}
      <input type="hidden" name="category" value={value} />
    </div>
  );
};

export default CategorySelector;
