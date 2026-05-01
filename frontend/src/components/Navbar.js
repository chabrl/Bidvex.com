import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { 
  Moon, Sun, User, LogOut, LayoutDashboard, 
  MessageCircle, DollarSign, Shield, Lock, Menu, X,
  Home, ShoppingBag, Gavel, ChevronDown, Car, Building2
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, 
  DropdownMenuTrigger, DropdownMenuSeparator 
} from './ui/dropdown-menu';
import SellOptionsModal from './SellOptionsModal';
import NotificationCenter from './NotificationCenter';
import useFeatureFlag from '../hooks/useFeatureFlag';

const Navbar = () => {
  const { t, i18n } = useTranslation();
  const { user, logout, updateUserPreferences } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [sellModalOpen, setSellModalOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const changeLanguage = async (lng) => {
    i18n.changeLanguage(lng);
    if (user) {
      try {
        await updateUserPreferences({ preferred_language: lng });
      } catch (error) {
        console.error('Failed to save language preference:', error);
      }
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const isActive = (path) => location.pathname === path;

  // iter176 — surface "SOON · BIENTÔT" badge when the feature flag is off
  const { enabled: vehicleEnabled } = useFeatureFlag('vehicle_auctions_enabled');
  const showVehicleComingSoon = vehicleEnabled === false;

  const navLinks = [
    { path: '/', label: t('nav.home'), icon: Home },
    { path: '/marketplace', label: t('nav.marketplace'), icon: ShoppingBag },
    { path: '/lots', label: t('nav.lotsAuction'), icon: Gavel },
    { path: '/storage-auctions', label: t('nav.storageAuctions', 'Storage Auctions'), icon: Lock },
    { path: '/vehicle-auctions', label: t('vehicles.vehicleAuctions'), icon: Car, comingSoon: showVehicleComingSoon },
  ];

  return (
    <>
      <nav 
        className={`fixed top-0 left-0 right-0 z-[70] transition-all duration-300 ${
          scrolled 
            ? 'glassmorphism shadow-md' 
            : 'bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm shadow-sm'
        }`}
        data-testid="main-navbar"
      >
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8">
          <div className="flex justify-between items-center h-14 sm:h-16">
            {/* Logo */}
            <Link 
              to="/" 
              className="flex items-center space-x-2 group flex-shrink-0" 
              data-testid="nav-logo"
            >
              <img 
                src="/bidvex-logo.webp" 
                alt="BidVex" 
                width={233}
                height={56}
                className="h-8 sm:h-9 w-auto transform group-hover:scale-105 transition-transform duration-200"
                fetchpriority="high"
              />
            </Link>

            {/* Desktop Navigation — visible at lg+ to avoid tablet overflow */}
            <div className="hidden lg:flex items-center space-x-1">
              {navLinks.map((link) => (
                <Link key={link.path} to={link.path} data-testid={`nav-${link.path.replace('/', '') || 'home'}-link`}>
                  <Button 
                    variant="ghost" 
                    className={`text-sm font-medium transition-all duration-200 whitespace-nowrap ${
                      isActive(link.path) 
                        ? 'text-primary bg-primary/10' 
                        : 'text-foreground/80 hover:text-foreground hover:bg-accent'
                    }`}
                  >
                    <link.icon className="w-4 h-4 mr-1.5" />
                    {link.label}
                    {link.comingSoon && (
                      <span
                        className="ml-1.5 inline-flex items-center rounded-full bg-cyan-500/15 border border-cyan-500/40 text-cyan-700 dark:text-cyan-300 px-1.5 py-[1px] font-bold"
                        style={{ fontSize: '10px', lineHeight: 1.2, letterSpacing: '0.5px' }}
                        data-testid="nav-vehicle-coming-soon-badge"
                      >
                        SOON · BIENTÔT
                      </span>
                    )}
                  </Button>
                </Link>
              ))}
              {user && (
                <Button 
                  variant="ghost" 
                  className="text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent whitespace-nowrap"
                  onClick={() => setSellModalOpen(true)}
                  data-testid="nav-sell-button"
                >
                  <DollarSign className="w-4 h-4 mr-1.5" />
                  {t('nav.sell')}
                </Button>
              )}
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-0.5 sm:gap-1">
              {/* Messages — hide on small mobile */}
              {user && (
                <Link to="/messages" data-testid="messages-link" className="hidden sm:block">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="relative hover:bg-slate-100 dark:hover:bg-slate-800 navbar-icon-btn h-9 w-9"
                  >
                    <MessageCircle className="h-4 w-4 sm:h-5 sm:w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                  </Button>
                </Link>
              )}

              {/* Theme Toggle — hide on very small screens */}
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={toggleTheme} 
                data-testid="theme-toggle-btn"
                aria-label="Toggle theme"
                className="hidden sm:inline-flex transition-transform hover:scale-110 hover:bg-slate-100 dark:hover:bg-slate-800 navbar-icon-btn h-9 w-9"
              >
                {theme === 'light' ? (
                  <Moon className="h-4 w-4 sm:h-5 sm:w-5 navbar-icon text-slate-900" />
                ) : (
                  <Sun className="h-4 w-4 sm:h-5 sm:w-5 navbar-icon text-slate-100" />
                )}
              </Button>

              {/* Language Toggle */}
              <div 
                className="flex items-center border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden"
                data-testid="language-toggle"
              >
                <button
                  onClick={() => changeLanguage('en')}
                  data-testid="language-en-btn"
                  className={`px-2 py-1 sm:px-2.5 sm:py-1.5 text-xs font-semibold transition-all duration-200 ${
                    i18n.language === 'en' || i18n.language?.startsWith('en')
                      ? 'bg-primary text-white'
                      : 'bg-transparent text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  EN
                </button>
                <div className="w-px h-4 sm:h-5 bg-slate-200 dark:bg-slate-700" />
                <button
                  onClick={() => changeLanguage('fr')}
                  data-testid="language-fr-btn"
                  className={`px-2 py-1 sm:px-2.5 sm:py-1.5 text-xs font-semibold transition-all duration-200 ${
                    i18n.language === 'fr' || i18n.language?.startsWith('fr')
                      ? 'bg-primary text-white'
                      : 'bg-transparent text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  FR
                </button>
              </div>

              {/* Notification Center */}
              {user && <NotificationCenter />}

              {/* User Menu */}
              {user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      data-testid="user-menu-btn"
                      className="relative hover:bg-slate-100 dark:hover:bg-slate-800 h-9 w-9"
                    >
                      {user.picture ? (
                        <img 
                          src={user.picture} 
                          alt={user.name} 
                          className="h-7 w-7 sm:h-8 sm:w-8 rounded-full ring-2 ring-blue-500/30" 
                        />
                      ) : (
                        <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-md">
                          <User className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-white" />
                        </div>
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64">
                    <div className="px-3 py-3 border-b border-border">
                      <p className="font-semibold text-foreground">{user.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{user.email}</p>
                    </div>
                    {/* Mobile-only items: Messages & Theme */}
                    <div className="sm:hidden py-1 border-b border-border">
                      <DropdownMenuItem onClick={() => navigate('/messages')} className="cursor-pointer">
                        <MessageCircle className="mr-3 h-4 w-4 text-muted-foreground" />
                        Messages
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={toggleTheme} className="cursor-pointer">
                        {theme === 'light' ? <Moon className="mr-3 h-4 w-4 text-muted-foreground" /> : <Sun className="mr-3 h-4 w-4 text-muted-foreground" />}
                        {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
                      </DropdownMenuItem>
                    </div>
                    <div className="py-2">
                      <DropdownMenuItem onClick={() => navigate('/seller/dashboard')} data-testid="seller-dashboard-link" className="cursor-pointer">
                        <LayoutDashboard className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.sellerDashboard')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => navigate('/buyer/dashboard')} data-testid="buyer-dashboard-link" className="cursor-pointer">
                        <ShoppingBag className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.buyerDashboard')}
                      </DropdownMenuItem>
                    </div>
                    {(user.is_partner || user.role === 'admin' || user.role === 'superadmin') && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => navigate('/partner/dashboard')} data-testid="partner-dashboard-link" className="cursor-pointer text-blue-600 font-semibold">
                          <Shield className="mr-3 h-4 w-4" />
                          Partner Dashboard
                        </DropdownMenuItem>
                      </>
                    )}
                    {(user.role === 'admin' || user.role === 'superadmin' || user.account_type === 'admin' || user.email?.endsWith('@admin.bazario.com')) && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => navigate('/admin')} data-testid="admin-dashboard-link" className="cursor-pointer text-primary font-semibold">
                          <Shield className="mr-3 h-4 w-4" />
                          {t('nav.adminPanel')}
                        </DropdownMenuItem>
                      </>
                    )}
                    <DropdownMenuSeparator />
                    <div className="py-2">
                      <DropdownMenuItem onClick={() => navigate('/settings')} data-testid="settings-link" className="cursor-pointer">
                        <User className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('admin.settings')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => navigate('/affiliate')} data-testid="affiliate-link" className="cursor-pointer">
                        <DollarSign className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.affiliateDashboard')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => navigate('/become-a-partner')} data-testid="become-partner-link" className="cursor-pointer">
                        <Building2 className="mr-3 h-4 w-4 text-muted-foreground" />
                        Become a Partner
                      </DropdownMenuItem>
                    </div>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleLogout} data-testid="logout-btn" className="cursor-pointer text-destructive focus:text-destructive">
                      <LogOut className="mr-3 h-4 w-4" />
                      {t('nav.logout')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Link to="/auth" data-testid="login-link">
                  <Button className="gradient-button text-white border-0 h-9 sm:h-10 min-h-[44px] px-3 sm:px-4 text-sm">
                    {t('nav.login')}
                  </Button>
                </Link>
              )}

              {/* Mobile Menu Toggle — visible below lg */}
              <Button 
                variant="ghost" 
                size="icon" 
                className="lg:hidden navbar-icon-btn hover:bg-slate-100 dark:hover:bg-slate-800 h-9 w-9"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                data-testid="mobile-menu-toggle"
                aria-label="Toggle mobile menu"
              >
                {mobileMenuOpen ? (
                  <X className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                ) : (
                  <Menu className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile/Tablet Menu — shown below lg */}
        {mobileMenuOpen && (
          <div className="lg:hidden bg-card border-t border-border animate-slideUp">
            <div className="px-4 py-3 space-y-1 max-w-7xl mx-auto">
              {navLinks.map((link) => (
                <Link 
                  key={link.path} 
                  to={link.path}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all min-h-[44px] ${
                    isActive(link.path) 
                      ? 'bg-primary/10 text-primary font-medium' 
                      : 'text-foreground hover:bg-accent'
                  }`}
                >
                  <link.icon className="w-5 h-5 shrink-0" />
                  <span className="truncate">{link.label}</span>
                </Link>
              ))}
              {user && (
                <button 
                  onClick={() => {
                    setSellModalOpen(true);
                    setMobileMenuOpen(false);
                  }}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl text-foreground hover:bg-accent w-full text-left min-h-[44px]"
                >
                  <DollarSign className="w-5 h-5 shrink-0" />
                  <span>{t('nav.sell')}</span>
                </button>
              )}
            </div>
          </div>
        )}
      </nav>

      {/* Spacer for fixed navbar */}
      <div className="h-14 sm:h-16" />

      {/* Sell Options Modal */}
      <SellOptionsModal 
        isOpen={sellModalOpen} 
        onClose={() => setSellModalOpen(false)} 
      />
    </>
  );
};

export default Navbar;
