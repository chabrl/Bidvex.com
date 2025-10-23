import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Moon, Sun, Globe, User, LogOut, LayoutDashboard, Menu, X, MessageCircle, DollarSign } from 'lucide-react';
import { Button } from './ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from './ui/dropdown-menu';

const Navbar = () => {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const changeLanguage = (lng) => {
    i18n.changeLanguage(lng);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <nav className="sticky top-0 z-50 glassmorphism shadow-sm" data-testid="main-navbar">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center space-x-2 group" data-testid="nav-logo">
            <div className="gradient-bg w-10 h-10 rounded-xl flex items-center justify-center transform group-hover:rotate-6 transition-transform">
              <span className="text-white font-bold text-xl">B</span>
            </div>
            <span className="text-2xl font-bold gradient-text">Bazario</span>
          </Link>

          <div className="hidden md:flex items-center space-x-1">
            <Link to="/" data-testid="nav-home-link">
              <Button variant="ghost" className="text-sm font-medium">
                {t('nav.home')}
              </Button>
            </Link>
            <Link to="/marketplace" data-testid="nav-marketplace-link">
              <Button variant="ghost" className="text-sm font-medium">
                {t('nav.marketplace')}
              </Button>
            </Link>
            <Link to="/lots" data-testid="nav-lots-link">
              <Button variant="ghost" className="text-sm font-medium">
                {t('nav.lots', 'Lots Auction')}
              </Button>
            </Link>
            {user && user.account_type === 'business' && (
              <Link to="/create-multi-item-listing" data-testid="nav-multi-sell-link">
                <Button variant="ghost" className="text-sm font-medium">
                  Create Multi-Item
                </Button>
              </Link>
            )}
            {user && (
              <Link to="/create-listing" data-testid="nav-sell-link">
                <Button variant="ghost" className="text-sm font-medium">
                  {t('nav.sell')}
                </Button>
              </Link>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {user && (
              <Link to="/messages" data-testid="messages-link">
                <Button variant="ghost" size="icon">
                  <MessageCircle className="h-5 w-5" />
                </Button>
              </Link>
            )}
            <Button variant="ghost" size="icon" onClick={toggleTheme} data-testid="theme-toggle-btn">
              {theme === 'light' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" data-testid="language-toggle-btn">
                  <Globe className="h-5 w-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => changeLanguage('en')}>English</DropdownMenuItem>
                <DropdownMenuItem onClick={() => changeLanguage('fr')}>Français</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" data-testid="user-menu-btn">
                    {user.picture ? (
                      <img src={user.picture} alt={user.name} className="h-8 w-8 rounded-full" />
                    ) : (
                      <User className="h-5 w-5" />
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <div className="px-2 py-2">
                    <p className="font-medium">{user.name}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/seller/dashboard')} data-testid="seller-dashboard-link">
                    <LayoutDashboard className="mr-2 h-4 w-4" />
                    {t('nav.sellerDashboard')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/buyer/dashboard')} data-testid="buyer-dashboard-link">
                    <LayoutDashboard className="mr-2 h-4 w-4" />
                    {t('nav.buyerDashboard')}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/settings')} data-testid="settings-link">
                    <User className="mr-2 h-4 w-4" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/affiliate')} data-testid="affiliate-link">
                    <DollarSign className="mr-2 h-4 w-4" />
                    Affiliate Program
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} data-testid="logout-btn">
                    <LogOut className="mr-2 h-4 w-4" />
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

            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} data-testid="mobile-menu-btn">
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t">
            <div className="flex flex-col space-y-2">
              <Link to="/" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="ghost" className="w-full justify-start">
                  {t('nav.home')}
                </Button>
              </Link>
              <Link to="/marketplace" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="ghost" className="w-full justify-start">
                  {t('nav.marketplace')}
                </Button>
              </Link>
              {user && (
                <Link to="/create-listing" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="ghost" className="w-full justify-start">
                    {t('nav.sell')}
                  </Button>
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
