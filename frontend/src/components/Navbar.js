import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { 
  Moon, Sun, Globe, User, LogOut, LayoutDashboard, 
  MessageCircle, DollarSign, Shield, Menu, X,
  Home, ShoppingBag, Gavel, ChevronDown
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { 
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, 
  DropdownMenuTrigger, DropdownMenuSeparator 
} from './ui/dropdown-menu';
import SellOptionsModal from './SellOptionsModal';
import NotificationCenter from './NotificationCenter';
const Navbar = () => {
  const { t, i18n } = useTranslation();
  const { user, logout, updateUserPreferences } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [sellModalOpen, setSellModalOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [searchOpen] = useState(false); // Kept for compatibility, not used

  // Handle scroll effect
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
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

  const navLinks = [
    { path: '/', label: t('nav.home'), icon: Home },
    { path: '/marketplace', label: t('nav.marketplace'), icon: ShoppingBag },
    { path: '/lots', label: t('nav.lotsAuction'), icon: Gavel },
  ];

  return (
    <>
      <nav 
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled 
            ? 'glassmorphism shadow-md' 
            : 'bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm shadow-sm'
        }`}
        data-testid="main-navbar"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <Link 
              to="/" 
              className="flex items-center space-x-3 group flex-shrink-0" 
              data-testid="nav-logo"
            >
              <img 
                src="/bidvex-logo.png" 
                alt="BidVex" 
                className="h-9 w-auto transform group-hover:scale-105 transition-transform duration-200"
              />
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center space-x-1">
              {navLinks.map((link) => (
                <Link key={link.path} to={link.path} data-testid={`nav-${link.path.replace('/', '') || 'home'}-link`}>
                  <Button 
                    variant="ghost" 
                    className={`text-sm font-medium transition-all duration-200 ${
                      isActive(link.path) 
                        ? 'text-primary bg-primary/10' 
                        : 'text-foreground/80 hover:text-foreground hover:bg-accent'
                    }`}
                  >
                    <link.icon className="w-4 h-4 mr-2" />
                    {link.label}
                  </Button>
                </Link>
              ))}
              {user && (
                <Button 
                  variant="ghost" 
                  className="text-sm font-medium text-foreground/80 hover:text-foreground hover:bg-accent"
                  onClick={() => setSellModalOpen(true)}
                  data-testid="nav-sell-button"
                >
                  <DollarSign className="w-4 h-4 mr-2" />
                  {t('nav.sell')}
                </Button>
              )}
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center space-x-1">
              {/* Messages */}
              {user && (
                <Link to="/messages" data-testid="messages-link">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="relative hover:bg-slate-100 dark:hover:bg-slate-800 navbar-icon-btn"
                  >
                    <MessageCircle className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                  </Button>
                </Link>
              )}

              {/* Theme Toggle */}
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={toggleTheme} 
                data-testid="theme-toggle-btn"
                className="transition-transform hover:scale-110 hover:bg-slate-100 dark:hover:bg-slate-800 navbar-icon-btn"
              >
                {theme === 'light' ? (
                  <Moon className="h-5 w-5 navbar-icon text-slate-900" />
                ) : (
                  <Sun className="h-5 w-5 navbar-icon text-slate-100" />
                )}
              </Button>

              {/* Language Selector */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    data-testid="language-toggle-btn" 
                    className="hover:bg-slate-100 dark:hover:bg-slate-800 navbar-icon-btn"
                  >
                    <Globe className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-40">
                  <DropdownMenuItem 
                    onClick={() => changeLanguage('en')}
                    className={i18n.language === 'en' ? 'bg-accent' : ''}
                  >
                    🇬🇧 English
                  </DropdownMenuItem>
                  <DropdownMenuItem 
                    onClick={() => changeLanguage('fr')}
                    className={i18n.language === 'fr' ? 'bg-accent' : ''}
                  >
                    🇫🇷 Français
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Notification Center (Bell Icon) */}
              {user && <NotificationCenter />}

              {/* User Menu */}
              {user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      data-testid="user-menu-btn"
                      className="relative hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      {user.picture ? (
                        <img 
                          src={user.picture} 
                          alt={user.name} 
                          className="h-8 w-8 rounded-full ring-2 ring-blue-500/30" 
                        />
                      ) : (
                        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center shadow-md">
                          <User className="h-4 w-4 text-white" />
                        </div>
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64">
                    <div className="px-3 py-3 border-b border-border">
                      <p className="font-semibold text-foreground">{user.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <div className="py-2">
                      <DropdownMenuItem 
                        onClick={() => navigate('/seller/dashboard')} 
                        data-testid="seller-dashboard-link"
                        className="cursor-pointer"
                      >
                        <LayoutDashboard className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.sellerDashboard')}
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        onClick={() => navigate('/buyer/dashboard')} 
                        data-testid="buyer-dashboard-link"
                        className="cursor-pointer"
                      >
                        <ShoppingBag className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.buyerDashboard')}
                      </DropdownMenuItem>
                    </div>
                    
                    {/* Admin Access */}
                    {(user.role === 'admin' || user.role === 'superadmin' || user.account_type === 'admin' || user.email?.endsWith('@admin.bazario.com')) && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem 
                          onClick={() => navigate('/admin')} 
                          data-testid="admin-dashboard-link"
                          className="cursor-pointer text-primary font-semibold"
                        >
                          <Shield className="mr-3 h-4 w-4" />
                          {t('nav.adminPanel')}
                        </DropdownMenuItem>
                      </>
                    )}
                    
                    <DropdownMenuSeparator />
                    <div className="py-2">
                      <DropdownMenuItem 
                        onClick={() => navigate('/settings')} 
                        data-testid="settings-link"
                        className="cursor-pointer"
                      >
                        <User className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('admin.settings')}
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        onClick={() => navigate('/affiliate')} 
                        data-testid="affiliate-link"
                        className="cursor-pointer"
                      >
                        <DollarSign className="mr-3 h-4 w-4 text-muted-foreground" />
                        {t('nav.affiliateDashboard')}
                      </DropdownMenuItem>
                    </div>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem 
                      onClick={handleLogout} 
                      data-testid="logout-btn"
                      className="cursor-pointer text-destructive focus:text-destructive"
                    >
                      <LogOut className="mr-3 h-4 w-4" />
                      {t('nav.logout')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Link to="/auth" data-testid="login-link">
                  <Button className="gradient-button text-white border-0" size="sm">
                    {t('nav.login')}
                  </Button>
                </Link>
              )}

              {/* Mobile Menu Toggle */}
              <Button 
                variant="ghost" 
                size="icon" 
                className="md:hidden navbar-icon-btn hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? (
                  <X className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                ) : (
                  <Menu className="h-5 w-5 navbar-icon text-slate-900 dark:text-slate-100" />
                )}
              </Button>
            </div>
          </div>

          {/* Search Bar - Expandable */}
          {searchOpen && (
            <div className="hidden md:block pb-4 animate-slideUp">
              <div className="relative max-w-xl mx-auto">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input 
                  placeholder="Search auctions, items, sellers..."
                  className="pl-10 bg-background/50 backdrop-blur-sm"
                  autoFocus
                />
              </div>
            </div>
          )}
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-card border-t border-border animate-slideUp">
            <div className="px-4 py-4 space-y-2">
              {navLinks.map((link) => (
                <Link 
                  key={link.path} 
                  to={link.path}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                    isActive(link.path) 
                      ? 'bg-primary/10 text-primary font-medium' 
                      : 'text-foreground hover:bg-accent'
                  }`}
                >
                  <link.icon className="w-5 h-5" />
                  {link.label}
                </Link>
              ))}
              {user && (
                <button 
                  onClick={() => {
                    setSellModalOpen(true);
                    setMobileMenuOpen(false);
                  }}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl text-foreground hover:bg-accent w-full text-left"
                >
                  <DollarSign className="w-5 h-5" />
                  {t('nav.sell')}
                </button>
              )}
              
              {/* Mobile Search */}
              <div className="px-4 py-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input 
                    placeholder="Search..."
                    className="pl-10"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Spacer for fixed navbar */}
      <div className="h-16" />

      {/* Sell Options Modal */}
      <SellOptionsModal 
        isOpen={sellModalOpen} 
        onClose={() => setSellModalOpen(false)} 
      />
    </>
  );
};

export default Navbar;
