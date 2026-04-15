import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useCategoryTree } from '../hooks/useCategoryTree';
import { Label } from '../components/ui/label';
import { ChevronRight, Loader2, ShieldAlert } from 'lucide-react';
import InfoTip from './InfoTip';

/**
 * Two-step category selector for seller flows.
 * Vehicle categories shown but BLOCKED for non-licensed users with compliance modal.
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
  const [showVehicleModal, setShowVehicleModal] = useState(false);

  useEffect(() => {
    if (!value || tree.length === 0) return;
    const parentNode = getParent(value);
    if (parentNode) {
      setSelectedParentId(parentNode.id);
      setSelectedChildName(value);
    } else {
      const root = tree.find(r => r.nameEn === value);
      if (root) {
        setSelectedParentId(root.id);
        setSelectedChildName(root.children.length === 0 ? value : '');
      }
    }
  }, [value, tree]);

  const isPartnerOrAdmin = userRole === 'partner' || userRole === 'admin';

  const isVehicleCategory = (cat) => {
    const name = (cat.nameEn || '').toLowerCase();
    return name === 'vehicle' || name === 'vehicles' || name === 'road_vehicles';
  };

  const selectedParent = tree.find(p => p.id === selectedParentId);
  const hasChildren = selectedParent?.children?.length > 0;

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
    const parent = tree.find(p => p.id === parentId);

    // Block vehicle selection for non-licensed users
    if (parent && isVehicleCategory(parent) && filterVehicles && !isPartnerOrAdmin) {
      setShowVehicleModal(true);
      return;
    }

    setSelectedParentId(parentId);
    setSelectedChildName('');

    if (parent && parent.children.length === 0) {
      onChange(parent.nameEn);
    } else {
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
      <div className="flex items-center gap-1.5">
        <Label>{label || t('createListing.category', 'Category')} {required && '*'}</Label>
        <InfoTip
          en="Choose the category that best describes your item. Vehicle listings require a verified dealer license."
          fr="Choisissez la catégorie qui décrit le mieux votre article. Les annonces de véhicules nécessitent un permis de commerçant vérifié."
        />
      </div>

      {breadcrumb}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <select
            value={selectedParentId}
            onChange={handleParentChange}
            className="w-full px-3 py-2 border border-input rounded-md bg-background text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
            data-testid="category-parent-select"
            required={required}
          >
            <option value="">{t('createListing.selectCategory', 'Select category...')}</option>
            {tree.map(parent => {
              const blocked = isVehicleCategory(parent) && filterVehicles && !isPartnerOrAdmin;
              return (
                <option key={parent.id} value={parent.id} className={blocked ? 'text-slate-400' : ''}>
                  {parent.icon} {getName(parent)} {blocked ? '🔒' : ''}
                </option>
              );
            })}
          </select>
        </div>

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

      <input type="hidden" name="category" value={value} />

      {/* Vehicle Restriction Modal */}
      {showVehicleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" data-testid="vehicle-restriction-modal">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md mx-4 p-6 space-y-4 border border-red-200 dark:border-red-800">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center shrink-0">
                <ShieldAlert className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-slate-900 dark:text-white">
                  {t('vehicleRestriction.title', 'Vehicle Listing Restricted')}
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t('vehicleRestriction.subtitle', 'Compliance Requirement')}
                </p>
              </div>
            </div>

            <div className="space-y-3 text-sm">
              <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                You must be a licensed vehicle dealer to list vehicles on BidVex. This is required by Quebec's Office de la protection du consommateur (OPC).
              </p>
              <p className="text-slate-700 dark:text-slate-300 leading-relaxed" lang="fr">
                Vous devez être un commerçant de véhicules d'occasion autorisé pour publier des véhicules sur BidVex. Cette exigence est imposée par l'Office de la protection du consommateur (OPC) du Québec.
              </p>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <a
                href="/become-vehicle-seller"
                className="inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-primary text-white font-medium text-sm hover:bg-primary/90 transition-colors"
                data-testid="apply-vehicle-dealer-btn"
              >
                {t('vehicleRestriction.apply', 'Apply as Licensed Vehicle Dealer')}
              </a>
              <button
                onClick={() => setShowVehicleModal(false)}
                className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
                data-testid="close-vehicle-modal-btn"
              >
                {t('common.close', 'Close')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CategorySelector;
