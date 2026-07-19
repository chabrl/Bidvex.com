/**
 * iter363 — AdminSidebar.
 *
 * Converts the horizontal PRIMARY/SECONDARY tab strip into a professional
 * left sidebar with collapsible mobile behaviour. Preserves the exact
 * same PRIMARY / SECONDARY / MARKETING / FINANCIAL grouping the admin
 * console has always shipped with — no data model change, only layout.
 *
 * Props:
 *   - primaryTabs:   [{ id, label, icon, lucideIcon }]
 *   - secondaryTabs: { [primaryId]: [{ id, label, icon, lucideIcon }] }
 *   - marketingTabs: [{ id, label, icon, lucideIcon }]
 *   - financialTabs: [{ id, label, icon, lucideIcon }]
 *   - primaryTab:    active primary id
 *   - secondaryTab:  active secondary id
 *   - onPrimaryClick(id): activates a primary section (also flips to its first secondary)
 *   - onSecondaryClick(id): activates a secondary tab
 *   - pendingDealerLicenses: int, shows a red count badge on Vehicles
 *   - open (mobile):   controls the sliding drawer on <lg screens
 *   - onClose:         called when user taps backdrop / close button on mobile
 */
import React, { useMemo } from 'react';
import { ChevronRight, X, Sparkles } from 'lucide-react';

const SectionLabel = ({ children, color = 'slate' }) => (
  <div
    className={`px-4 mt-4 mb-1 text-[10px] font-semibold uppercase tracking-wider text-${color}-500`}
  >
    {children}
  </div>
);

const NavButton = ({
  active, icon, lucideIcon: Lucide, label, badge, onClick, testId, tone = 'default',
}) => {
  const toneMap = {
    default: {
      active:  'bg-primary text-white shadow-lg',
      inactive:'text-slate-700 hover:bg-slate-100',
    },
    marketing: {
      active:  'bg-amber-500 text-white shadow-lg',
      inactive:'text-amber-800 hover:bg-amber-100',
    },
    finance: {
      active:  'bg-emerald-500 text-white shadow-lg',
      inactive:'text-emerald-800 hover:bg-emerald-100',
    },
    secondary: {
      active:  'bg-white text-primary shadow border border-primary/20',
      inactive:'text-slate-600 hover:bg-white hover:shadow-sm',
    },
  };
  const cls = active ? toneMap[tone].active : toneMap[tone].inactive;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative w-full flex items-center gap-2 px-3 py-2 rounded-lg font-medium text-sm transition-all text-left min-h-[44px] ${cls}`}
      data-testid={testId}
    >
      {Lucide ? <Lucide className="h-4 w-4 flex-shrink-0" /> : <span className="text-base">{icon}</span>}
      <span className="truncate">{label}</span>
      {typeof badge === 'number' && badge > 0 && (
        <span className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-red-600 text-white text-[10px] font-bold ring-2 ring-white">
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </button>
  );
};

export default function AdminSidebar({
  primaryTabs,
  secondaryTabs,
  marketingTabs = [],
  financialTabs = [],
  primaryTab,
  secondaryTab,
  onPrimaryClick,
  onSecondaryClick,
  pendingDealerLicenses = 0,
  open = false,
  onClose = () => {},
}) {
  const activeSecondaryList = useMemo(
    () => secondaryTabs[primaryTab] || [],
    [secondaryTabs, primaryTab],
  );

  const drawer = (
    <aside
      className="h-full w-72 bg-white border-r border-slate-200 flex flex-col overflow-hidden"
      data-testid="admin-sidebar"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gradient-to-r from-primary/95 to-primary text-white flex-shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <span className="font-bold text-sm tracking-wide">Admin Console</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="lg:hidden p-1 rounded hover:bg-white/20"
          aria-label="Close menu"
          data-testid="admin-sidebar-close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Scrollable nav body */}
      <nav className="flex-1 overflow-y-auto py-2">
        <SectionLabel>Primary Sections</SectionLabel>
        <div className="px-2 space-y-1" data-testid="admin-sidebar-primary">
          {primaryTabs.map((tab) => {
            const isActive = primaryTab === tab.id;
            const badge = tab.id === 'vehicles' ? pendingDealerLicenses : undefined;
            return (
              <div key={tab.id}>
                <NavButton
                  active={isActive}
                  icon={tab.icon}
                  lucideIcon={tab.lucideIcon}
                  label={tab.label}
                  badge={badge}
                  onClick={() => onPrimaryClick(tab.id)}
                  testId={`admin-primary-tab-${tab.id}`}
                />
                {/* Inline secondary items under active primary */}
                {isActive && activeSecondaryList.length > 0 && (
                  <div className="mt-1 mb-2 ml-3 pl-3 border-l-2 border-primary/20 space-y-0.5"
                       data-testid="admin-sidebar-secondary">
                    {activeSecondaryList.map((sub) => (
                      <NavButton
                        key={sub.id}
                        active={secondaryTab === sub.id}
                        icon={sub.icon}
                        lucideIcon={sub.lucideIcon}
                        label={sub.label}
                        onClick={() => onSecondaryClick(sub.id)}
                        testId={`admin-tab-${sub.id}`}
                        tone="secondary"
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {marketingTabs.length > 0 && (
          <>
            <SectionLabel color="amber">Marketing</SectionLabel>
            <div className="px-2 space-y-1" data-testid="admin-sidebar-marketing">
              {marketingTabs.map((tab) => (
                <NavButton
                  key={tab.id}
                  active={secondaryTab === tab.id}
                  icon={tab.icon}
                  lucideIcon={tab.lucideIcon}
                  label={tab.label}
                  onClick={() => onSecondaryClick(tab.id)}
                  testId={`admin-tab-${tab.id}`}
                  tone="marketing"
                />
              ))}
            </div>
          </>
        )}

        {financialTabs.length > 0 && (
          <>
            <SectionLabel color="emerald">Finance &amp; Safety</SectionLabel>
            <div className="px-2 space-y-1 pb-4" data-testid="admin-sidebar-finance">
              {financialTabs.map((tab) => (
                <NavButton
                  key={tab.id}
                  active={secondaryTab === tab.id}
                  icon={tab.icon}
                  lucideIcon={tab.lucideIcon}
                  label={tab.label}
                  onClick={() => onSecondaryClick(tab.id)}
                  testId={`admin-tab-${tab.id}`}
                  tone="finance"
                />
              ))}
            </div>
          </>
        )}
      </nav>

      {/* Footer breadcrumb hint */}
      <div className="border-t px-4 py-2 text-[11px] text-slate-500 flex items-center gap-1 flex-shrink-0">
        <ChevronRight className="h-3 w-3" />
        <span className="truncate">
          {primaryTabs.find((t) => t.id === primaryTab)?.label || 'Section'} ›{' '}
          {activeSecondaryList.find((s) => s.id === secondaryTab)?.label
            || marketingTabs.find((s) => s.id === secondaryTab)?.label
            || financialTabs.find((s) => s.id === secondaryTab)?.label
            || '—'}
        </span>
      </div>
    </aside>
  );

  return (
    <>
      {/* Desktop: static sidebar (>=lg) */}
      <div className="hidden lg:block lg:sticky lg:top-0 lg:h-screen flex-shrink-0">
        {drawer}
      </div>

      {/* Mobile: sliding drawer + backdrop */}
      <div
        className={`lg:hidden fixed inset-0 z-40 transition-opacity duration-200 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        data-testid="admin-sidebar-mobile-backdrop"
      >
        <div
          className="absolute inset-0 bg-black/40"
          onClick={onClose}
          role="presentation"
        />
        <div
          className={`absolute inset-y-0 left-0 transform transition-transform duration-200 ${
            open ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          {drawer}
        </div>
      </div>
    </>
  );
}
