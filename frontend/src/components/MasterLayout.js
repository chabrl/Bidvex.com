import React from 'react';

/**
 * MasterLayout - Unified layout wrapper for all pages
 * Provides consistent spacing, responsive grid, and page transitions
 */
const MasterLayout = ({ 
  children, 
  className = '',
  fullWidth = false,
  noPadding = false,
  withTransition = true 
}) => {
  return (
    <div 
      className={`
        min-h-screen bg-surface
        ${withTransition ? 'page-transition' : ''}
      `}
    >
      <main 
        className={`
          ${fullWidth ? '' : 'container-premium'}
          ${noPadding ? '' : 'py-6 md:py-8 lg:py-10'}
          ${className}
        `}
      >
        {children}
      </main>
    </div>
  );
};

/**
 * PageHeader - Consistent header for all pages
 */
export const PageHeader = ({ 
  title, 
  subtitle, 
  action,
  breadcrumb,
  className = ''
}) => {
  return (
    <div className={`mb-8 ${className}`}>
      {breadcrumb && (
        <nav className="text-sm text-muted-foreground mb-2">
          {breadcrumb}
        </nav>
      )}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-muted-foreground text-base md:text-lg">
              {subtitle}
            </p>
          )}
        </div>
        {action && (
          <div className="flex-shrink-0">
            {action}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * PageSection - Consistent section wrapper
 */
export const PageSection = ({ 
  title, 
  subtitle,
  action,
  children, 
  className = '' 
}) => {
  return (
    <section className={`mb-10 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-6">
          <div>
            {title && (
              <h2 className="text-xl md:text-2xl font-semibold text-foreground">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-1 text-muted-foreground">
                {subtitle}
              </p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
};

/**
 * ContentGrid - 12-column responsive grid
 */
export const ContentGrid = ({ 
  children, 
  cols = 4, 
  gap = 6,
  className = '' 
}) => {
  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
    5: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5',
    6: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6',
  };

  const gapSizes = {
    2: 'gap-2',
    4: 'gap-4',
    6: 'gap-6',
    8: 'gap-8',
  };

  return (
    <div className={`grid ${gridCols[cols] || gridCols[4]} ${gapSizes[gap] || gapSizes[6]} ${className}`}>
      {children}
    </div>
  );
};

/**
 * TwoColumnLayout - Sidebar + Main content
 */
export const TwoColumnLayout = ({ 
  sidebar, 
  children,
  sidebarWidth = '280px',
  stickyBar = false,
  className = '' 
}) => {
  return (
    <div className={`flex flex-col lg:flex-row gap-6 lg:gap-8 ${className}`}>
      <aside 
        className={`
          w-full lg:w-auto lg:flex-shrink-0
          ${stickyBar ? 'lg:sticky lg:top-24 lg:self-start' : ''}
        `}
        style={{ minWidth: sidebarWidth }}
      >
        {sidebar}
      </aside>
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
};

/**
 * Card - Premium card component
 */
export const PremiumCard = ({ 
  children, 
  className = '',
  hover = true,
  padding = true,
  onClick
}) => {
  return (
    <div 
      className={`
        ${hover ? 'premium-card' : 'premium-card-static'}
        ${padding ? 'p-6' : ''}
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
      onClick={onClick}
    >
      {children}
    </div>
  );
};

/**
 * EmptyState - Consistent empty state component
 */
export const EmptyState = ({ 
  icon: Icon, 
  title, 
  description, 
  action 
}) => {
  return (
    <div className="empty-state">
      {Icon && <Icon className="empty-state-icon" />}
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-description">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
};

/**
 * LoadingGrid - Skeleton loading for grid layouts
 */
export const LoadingGrid = ({ count = 8, cols = 4 }) => {
  return (
    <ContentGrid cols={cols}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton-image" />
          <div className="p-4 space-y-3">
            <div className="skeleton-text full" />
            <div className="skeleton-text medium" />
            <div className="skeleton-text short" />
          </div>
        </div>
      ))}
    </ContentGrid>
  );
};

export default MasterLayout;
