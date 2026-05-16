import React, { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import "./FilterBar.css";

const SORT_OPTIONS = [
  { value: "nearby_first", label_en: "Nearby First", label_fr: "À proximité d'abord" },
  { value: "ending_soon", label_en: "Ending Soon", label_fr: "Se termine bientôt" },
  { value: "newest", label_en: "Newest First", label_fr: "Plus récent" },
  { value: "price", label_en: "Price: Low → High", label_fr: "Prix : Croissant" },
  { value: "-price", label_en: "Price: High → Low", label_fr: "Prix : Décroissant" },
  { value: "most_bids", label_en: "Most Bids", label_fr: "Plus d'offres" },
  { value: "-promoted", label_en: "Featured First", label_fr: "En vedette" },
];

const TAX_STATUS_OPTIONS = [
  { value: "", label_en: "All Listings", label_fr: "Toutes annonces" },
  { value: "partner", label_en: "Partner Auctions", label_fr: "Enchères partenaires" },
  { value: "standard", label_en: "Standard (Individual + Enterprise)", label_fr: "Standard (Individuel + Entreprise)" },
];

const CATEGORY_OPTIONS = [
  { value: "", label_en: "All Categories", label_fr: "Toutes catégories" },
  { value: "Heavy Equipment", label_en: "Heavy Equipment", label_fr: "Équipement lourd" },
  { value: "Industrial Equipment", label_en: "Industrial Equipment", label_fr: "Équipement industriel" },
  { value: "Business & Industrial", label_en: "Business & Industrial", label_fr: "Affaires & Industriel" },
  { value: "Home & Garden", label_en: "Home & Garden", label_fr: "Maison & Jardin" },
  { value: "Toys & Games", label_en: "Toys & Games", label_fr: "Jouets & Jeux" },
  { value: "Electronics", label_en: "Electronics", label_fr: "Électronique" },
  { value: "Building Materials", label_en: "Building Materials", label_fr: "Matériaux de construction" },
  { value: "Sports", label_en: "Sports", label_fr: "Sports" },
  { value: "Fashion", label_en: "Fashion", label_fr: "Mode" },
  { value: "Books & Media", label_en: "Books & Media", label_fr: "Livres & Médias" },
];

const CONDITION_OPTIONS = [
  { value: "", label_en: "All Conditions", label_fr: "Tous états" },
  { value: "new", label_en: "New", label_fr: "Neuf" },
  { value: "like_new", label_en: "Like New", label_fr: "Comme neuf" },
  { value: "good", label_en: "Good", label_fr: "Bon état" },
  { value: "fair", label_en: "Fair", label_fr: "État correct" },
  { value: "for_parts", label_en: "For Parts", label_fr: "Pour pièces" },
];

const PROVINCE_OPTIONS = [
  { value: "", label_en: "All Provinces", label_fr: "Toutes provinces" },
  { value: "QC", label_en: "Quebec", label_fr: "Québec" },
  { value: "ON", label_en: "Ontario", label_fr: "Ontario" },
  { value: "BC", label_en: "British Columbia", label_fr: "Colombie-Britannique" },
  { value: "AB", label_en: "Alberta", label_fr: "Alberta" },
  { value: "MB", label_en: "Manitoba", label_fr: "Manitoba" },
  { value: "SK", label_en: "Saskatchewan", label_fr: "Saskatchewan" },
  { value: "NS", label_en: "Nova Scotia", label_fr: "Nouvelle-Écosse" },
  { value: "NB", label_en: "New Brunswick", label_fr: "Nouveau-Brunswick" },
  { value: "NL", label_en: "Newfoundland", label_fr: "Terre-Neuve" },
  { value: "PE", label_en: "PEI", label_fr: "Île-du-Prince-Édouard" },
];

const TOGGLE_PILLS = [
  { key: "private_sales_only", icon: "👤", label_en: "Private Sales", label_fr: "Ventes privées", tooltip_en: "Show private seller listings only", tooltip_fr: "Annonces de vendeurs privés uniquement" },
  { key: "zero_fee_only", icon: "🏷️", label_en: "0% Buyer Fee", label_fr: "0% frais acheteur", tooltip_en: "Partner listings — no buyer premium", tooltip_fr: "Annonces partenaires — aucuns frais" },
  { key: "lots_auction", icon: "📦", label_en: "Lots Auction", label_fr: "Enchères par lot", tooltip_en: "Multi-item lot auctions only", tooltip_fr: "Enchères multi-articles uniquement" },
  { key: "no_taxes", icon: "✅", label_en: "No Taxes", label_fr: "Sans taxes", tooltip_en: "Private sale — no QST/HST", tooltip_fr: "Vente privée — sans TVQ/TVH" },
];

const FilterBar = ({ onFilterChange, pageContext = "marketplace" }) => {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith("fr") ? "fr" : "en";
  const t = (item) => item[`label_${lang}`];

  const [filters, setFilters] = useState({
    private_sales_only: false,
    zero_fee_only: false,
    lots_auction: pageContext === "lots",
    no_taxes: false,
    search: "",
    category: "",
    condition: "",
    sort: "nearby_first",
    province: "",
    tax_status: "",
  });

  const [mobileExpanded, setMobileExpanded] = useState(false);
  const searchRef = useRef(null);

  const activeCount = [
    filters.private_sales_only,
    filters.zero_fee_only,
    filters.lots_auction && pageContext !== "lots",
    filters.no_taxes,
    filters.search !== "",
    filters.category !== "",
    filters.condition !== "",
    filters.sort !== "nearby_first",
    filters.province !== "",
    filters.tax_status !== "",
  ].filter(Boolean).length;

  useEffect(() => {
    onFilterChange?.(filters);
    // Phase 5 — Meta Pixel Search event (only when a real search is happening)
    if (filters.search || filters.province || filters.category) {
      import('../../utils/metaPixel').then(({ trackSearch }) => {
        trackSearch({
          searchString: filters.search,
          category: filters.category,
          province: filters.province,
        });
      }).catch(() => {});
    }
  }, [filters]);

  const toggle = (key) => setFilters((prev) => ({ ...prev, [key]: !prev[key] }));
  const set = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const clearAll = () =>
    setFilters({
      private_sales_only: false, zero_fee_only: false,
      lots_auction: pageContext === "lots", no_taxes: false,
      search: "", category: "", condition: "", sort: "nearby_first", province: "",
      tax_status: "",
    });

  const pillCls = (active) => `filter-pill ${active ? "filter-pill--active" : ""}`;

  const renderPills = () =>
    TOGGLE_PILLS.map((pill) =>
      pill.key === "lots_auction" && pageContext === "lots" ? null : (
        <button key={pill.key} className={pillCls(filters[pill.key])} onClick={() => toggle(pill.key)}
          title={pill[`tooltip_${lang}`]} aria-pressed={filters[pill.key]} data-testid={`pill-${pill.key}`}>
          <span className="filter-pill__icon">{pill.icon}</span>
          <span className="filter-pill__label">{t(pill)}</span>
        </button>
      )
    );

  const renderSearch = (mobile) => (
    <div className={`filter-bar__search ${mobile ? "filter-bar__search--mobile" : ""}`}>
      <span className="filter-bar__search-icon">🔍</span>
      <input ref={mobile ? null : searchRef} type="text" className="filter-bar__search-input"
        placeholder={lang === "fr" ? "Rechercher..." : "Search items..."}
        value={filters.search} onChange={(e) => set("search", e.target.value)} data-testid="filter-search" />
      {filters.search && (
        <button className="filter-bar__search-clear" onClick={() => set("search", "")} aria-label="Clear">✕</button>
      )}
    </div>
  );

  const renderSelects = () => (
    <>
      <select className="filter-bar__select" value={filters.province} onChange={(e) => set("province", e.target.value)} data-testid="filter-province">
        {PROVINCE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o)}</option>)}
      </select>
      <select className="filter-bar__select" value={filters.category} onChange={(e) => set("category", e.target.value)} data-testid="filter-category">
        {CATEGORY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o)}</option>)}
      </select>
      <select className="filter-bar__select" value={filters.condition} onChange={(e) => set("condition", e.target.value)} data-testid="filter-condition">
        {CONDITION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o)}</option>)}
      </select>
      <select className="filter-bar__select" value={filters.tax_status} onChange={(e) => set("tax_status", e.target.value)} data-testid="filter-tax-status" title={lang === "fr" ? "Statut fiscal" : "Tax Status"}>
        {TAX_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o)}</option>)}
      </select>
      <select className="filter-bar__select filter-bar__select--sort" value={filters.sort} onChange={(e) => set("sort", e.target.value)} data-testid="filter-sort">
        {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t(o)}</option>)}
      </select>
    </>
  );

  return (
    <div className="filter-bar-wrapper" data-testid="filter-bar">
      {/* Desktop */}
      <div className="filter-bar-desktop">
        <div className="filter-bar__pills">{renderPills()}</div>
        <div className="filter-bar__divider" />
        {renderSearch(false)}
        <div className="filter-bar__divider" />
        <div className="filter-bar__dropdowns">{renderSelects()}</div>
        {activeCount > 0 && (
          <button className="filter-bar__clear" onClick={clearAll} data-testid="filter-clear">
            ✕ {lang === "fr" ? "Effacer" : "Clear"} ({activeCount})
          </button>
        )}
      </div>

      {/* Mobile */}
      <div className="filter-bar-mobile">
        <div className="filter-bar-mobile__top">
          {renderSearch(true)}
          <button className="filter-bar-mobile__toggle" onClick={() => setMobileExpanded(!mobileExpanded)} aria-expanded={mobileExpanded} data-testid="filter-mobile-toggle">
            <span>⚙️ {lang === "fr" ? "Filtres" : "Filters"}</span>
            {activeCount > 0 && <span className="filter-bar-mobile__badge">{activeCount}</span>}
            <span className="filter-bar-mobile__chevron">{mobileExpanded ? "▲" : "▼"}</span>
          </button>
        </div>
        {mobileExpanded && (
          <div className="filter-bar-mobile__panel">
            <div className="filter-bar-mobile__pills">{renderPills()}</div>
            <div className="filter-bar-mobile__selects">{renderSelects()}</div>
            {activeCount > 0 && (
              <button className="filter-bar__clear filter-bar__clear--mobile" onClick={clearAll}>
                ✕ {lang === "fr" ? "Effacer tous les filtres" : "Clear all filters"} ({activeCount})
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default FilterBar;
