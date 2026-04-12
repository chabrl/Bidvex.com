import { useMemo } from 'react';
import { useCategories } from './useCategories';
import { useTranslation } from 'react-i18next';

/**
 * Builds a parent→children category tree from the flat categories list.
 * Returns { tree, flatList, isLoading } where tree is an array of root nodes,
 * each with a `children` array of subcategory nodes.
 *
 * Each node: { id, name, nameEn, nameFr, icon, parentId, children }
 */
export const useCategoryTree = () => {
  const { data: rawCategories = [], isLoading } = useCategories();
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  const { tree, flatMap } = useMemo(() => {
    const cats = Array.isArray(rawCategories) ? rawCategories : [];
    const map = {};
    const roots = [];

    // First pass: index all by id
    for (const cat of cats) {
      map[cat.id] = {
        id: cat.id,
        nameEn: cat.name_en || cat.name || '',
        nameFr: cat.name_fr || cat.name_en || cat.name || '',
        icon: cat.icon || '',
        parentId: cat.parent_id || null,
        order: cat.order ?? 999,
        children: [],
      };
    }

    // Second pass: attach children to parents
    for (const cat of cats) {
      const node = map[cat.id];
      if (node.parentId && map[node.parentId]) {
        map[node.parentId].children.push(node);
      } else if (!node.parentId) {
        roots.push(node);
      }
      // orphan children (parent_id doesn't match any root) — treat as roots
      else if (node.parentId && !map[node.parentId]) {
        roots.push(node);
      }
    }

    // Sort roots and children by order then name
    const sortFn = (a, b) => a.order - b.order || a.nameEn.localeCompare(b.nameEn);
    roots.sort(sortFn);
    for (const r of roots) {
      r.children.sort(sortFn);
    }

    return { tree: roots, flatMap: map };
  }, [rawCategories]);

  // Helper: get display name for a node based on current language
  const getName = (node) => {
    if (!node) return '';
    return lang === 'fr' ? (node.nameFr || node.nameEn) : node.nameEn;
  };

  // Helper: find a node by name_en (for matching existing category values)
  const findByNameEn = (nameEn) => {
    return Object.values(flatMap).find(n => n.nameEn === nameEn) || null;
  };

  // Helper: get parent node for a child
  const getParent = (childNameEn) => {
    const child = findByNameEn(childNameEn);
    if (!child || !child.parentId) return null;
    return flatMap[child.parentId] || null;
  };

  return { tree, isLoading, getName, findByNameEn, getParent, lang };
};
