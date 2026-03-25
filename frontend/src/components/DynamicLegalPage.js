import API_BASE from '../config';
/**
 * DynamicLegalPage - Modern Legal Page Component
 * Fully responsive with light/dark mode support
 * Features: Glassmorphism, sticky sidebar, scroll spy, WCAG AA compliant
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Loader2, ChevronRight, FileText, Shield, Scale, 
  BookOpen, AlertCircle, Clock, ChevronUp, Check,
  Menu, X
} from 'lucide-react';

const API = API_BASE;

// Section icons mapping
const SECTION_ICONS = {
  'information': FileText,
  'privacy': Shield,
  'terms': Scale,
  'rights': BookOpen,
  'liability': AlertCircle,
  'fees': FileText,
  'payment': FileText,
  'contact': FileText,
  'default': Check
};

const DynamicLegalPage = ({ pageKey, fallbackTitle, fallbackContent }) => {
  const { i18n } = useTranslation();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSection, setActiveSection] = useState('');
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const language = i18n.language || 'en';

  // Extract sections from HTML content for sidebar navigation
  const sections = useMemo(() => {
    if (!content?.content) return [];
    
    const parser = new DOMParser();
    const doc = parser.parseFromString(content.content, 'text/html');
    const headings = doc.querySelectorAll('h2, h3');
    
    return Array.from(headings).map((heading, index) => {
      const id = `section-${index}`;
      const text = heading.textContent?.trim() || '';
      const level = heading.tagName === 'H2' ? 2 : 3;
      
      // Determine icon based on content keywords
      let iconKey = 'default';
      const lowerText = text.toLowerCase();
      if (lowerText.includes('information') || lowerText.includes('collect') || lowerText.includes('données')) iconKey = 'information';
      else if (lowerText.includes('privacy') || lowerText.includes('data') || lowerText.includes('confidentialité')) iconKey = 'privacy';
      else if (lowerText.includes('terms') || lowerText.includes('condition') || lowerText.includes('acceptation')) iconKey = 'terms';
      else if (lowerText.includes('rights') || lowerText.includes('user') || lowerText.includes('droits')) iconKey = 'rights';
      else if (lowerText.includes('liability') || lowerText.includes('warranty') || lowerText.includes('responsabilité')) iconKey = 'liability';
      else if (lowerText.includes('fees') || lowerText.includes('frais') || lowerText.includes('payment') || lowerText.includes('paiement')) iconKey = 'fees';
      else if (lowerText.includes('contact')) iconKey = 'contact';
      
      return { id, text, level, iconKey };
    });
  }, [content]);

  // Inject IDs into content headings
  const processedContent = useMemo(() => {
    if (!content?.content) return fallbackContent;
    
    let html = content.content;
    let index = 0;
    
    // Add IDs to h2 and h3 tags
    html = html.replace(/<(h[23])([^>]*)>/gi, (match, tag, attrs) => {
      const id = `section-${index++}`;
      return `<${tag}${attrs} id="${id}">`;
    });
    
    return html;
  }, [content, fallbackContent]);

  useEffect(() => {
    fetchContent();
  }, [language, pageKey]);

  // Scroll spy for active section
  useEffect(() => {
    const handleScroll = () => {
      setShowBackToTop(window.scrollY > 300);
      
      // Find active section
      const scrollPosition = window.scrollY + 120;
      
      for (let i = sections.length - 1; i >= 0; i--) {
        const section = document.getElementById(sections[i].id);
        if (section && section.offsetTop <= scrollPosition) {
          setActiveSection(sections[i].id);
          break;
        }
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [sections]);

  const fetchContent = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(
        `${API}/site-config/legal-pages?language=${language}`
      );

      if (response.data.success && response.data.pages[pageKey]) {
        setContent(response.data.pages[pageKey]);
      } else {
        setContent({
          title: fallbackTitle,
          content: fallbackContent,
          link_type: 'page'
        });
      }
    } catch (err) {
      console.error('[DynamicLegalPage] Error fetching content:', err);
      setError(err.message);
      setContent({
        title: fallbackTitle,
        content: fallbackContent,
        link_type: 'page'
      });
    } finally {
      setLoading(false);
    }
  };

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      const offset = 100; // Account for sticky header
      const elementPosition = element.offsetTop - offset;
      window.scrollTo({ top: elementPosition, behavior: 'smooth' });
      setMobileNavOpen(false);
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">Loading content...</p>
        </div>
      </div>
    );
  }

  if (error && !content) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <Card className="max-w-lg">
          <CardContent className="pt-6">
            <p className="text-red-500 dark:text-red-400 mb-4">Failed to load content: {error}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Please try refreshing the page or contact support if the problem persists.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900" data-testid="legal-page">
      
      {/* Hero Section - Adaptive Light/Dark */}
      <div className="relative overflow-hidden">
        {/* Background Pattern - Subtle grid */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLDAsMCwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] dark:bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]" />
        
        {/* Gradient Orbs */}
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/10 dark:bg-primary/20 rounded-full blur-3xl" />
        <div className="absolute top-20 right-1/4 w-80 h-80 bg-cyan-500/10 dark:bg-cyan-500/15 rounded-full blur-3xl" />
        
        <div className="relative container mx-auto px-4 sm:px-6 lg:px-12 py-12 sm:py-16 lg:py-20">
          <div className="max-w-3xl mx-auto text-center">
            <Badge className="mb-4 bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary-foreground border-primary/20 backdrop-blur-sm">
              <FileText className="h-3 w-3 mr-1.5" />
              {language === 'fr' ? 'Document Juridique' : 'Legal Document'}
            </Badge>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white mb-4 tracking-tight">
              {content?.title || fallbackTitle}
            </h1>
            <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto leading-relaxed">
              {language === 'fr' 
                ? 'Veuillez lire attentivement ces conditions. En utilisant notre plateforme, vous acceptez d\'être lié par ces termes.'
                : 'Please read these terms carefully. By using our platform, you agree to be bound by these terms.'}
            </p>
            
            {/* Last Updated */}
            <div className="mt-6 inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <Clock className="h-4 w-4" />
              {language === 'fr' ? 'Dernière mise à jour' : 'Last updated'}: {new Date().toLocaleDateString(language === 'fr' ? 'fr-CA' : 'en-CA', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Toggle */}
      {sections.length > 0 && (
        <div className="lg:hidden sticky top-0 z-40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200 dark:border-slate-700">
          <div className="container mx-auto px-4">
            <button
              onClick={() => setMobileNavOpen(!mobileNavOpen)}
              className="w-full py-3 flex items-center justify-between text-slate-700 dark:text-slate-200"
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <FileText className="h-4 w-4" />
                {language === 'fr' ? 'Table des matières' : 'Table of Contents'}
              </span>
              {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            
            {/* Mobile Nav Dropdown */}
            {mobileNavOpen && (
              <div className="pb-4 max-h-[50vh] overflow-y-auto">
                {sections.map((section) => {
                  const Icon = SECTION_ICONS[section.iconKey] || Check;
                  const isActive = activeSection === section.id;
                  
                  return (
                    <button
                      key={section.id}
                      onClick={() => scrollToSection(section.id)}
                      className={`
                        w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-all
                        flex items-center gap-2
                        ${section.level === 3 ? 'ml-4' : ''}
                        ${isActive 
                          ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-foreground' 
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                        }
                      `}
                    >
                      <Icon className={`h-4 w-4 flex-shrink-0 ${isActive ? 'text-primary' : 'text-slate-400 dark:text-slate-500'}`} />
                      <span className="text-sm truncate">{section.text}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Content with Sidebar */}
      <div className="container mx-auto px-4 sm:px-6 lg:px-12 pb-12 lg:pb-16">
        <div className="flex flex-col lg:flex-row gap-8 max-w-7xl mx-auto">
          
          {/* Sticky Sidebar Navigation - Desktop Only */}
          {sections.length > 0 && (
            <aside className="hidden lg:block lg:w-72 flex-shrink-0">
              <div className="lg:sticky lg:top-24">
                {/* Glassmorphism Card - Light/Dark adaptive */}
                <div className="
                  bg-white/70 dark:bg-slate-800/70 
                  backdrop-blur-xl 
                  border border-slate-200/50 dark:border-slate-700/50 
                  rounded-2xl 
                  shadow-lg dark:shadow-2xl
                  overflow-hidden
                ">
                  <div className="p-4 border-b border-slate-200/50 dark:border-slate-700/50">
                    <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      {language === 'fr' ? 'Sommaire' : 'Contents'}
                    </h3>
                  </div>
                  <nav className="p-2 max-h-[60vh] overflow-y-auto">
                    {sections.map((section) => {
                      const Icon = SECTION_ICONS[section.iconKey] || Check;
                      const isActive = activeSection === section.id;
                      
                      return (
                        <button
                          key={section.id}
                          onClick={() => scrollToSection(section.id)}
                          className={`
                            w-full text-left px-3 py-2.5 rounded-xl mb-1 transition-all duration-200
                            flex items-center gap-2.5 group
                            ${section.level === 3 ? 'ml-4' : ''}
                            ${isActive 
                              ? 'bg-primary/10 dark:bg-primary/20 text-primary dark:text-blue-300 border-l-2 border-primary' 
                              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700/50'
                            }
                          `}
                          data-testid={`nav-${section.id}`}
                        >
                          <Icon className={`h-4 w-4 flex-shrink-0 transition-colors ${isActive ? 'text-primary dark:text-blue-400' : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300'}`} />
                          <span className="text-sm truncate leading-tight">{section.text}</span>
                          <ChevronRight className={`h-3 w-3 ml-auto flex-shrink-0 transition-transform opacity-0 group-hover:opacity-100 ${isActive ? 'opacity-100 rotate-90' : ''}`} />
                        </button>
                      );
                    })}
                  </nav>
                </div>
              </div>
            </aside>
          )}

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            {/* Content Card - Glassmorphism Light/Dark */}
            <div className="
              bg-white/70 dark:bg-slate-800/70 
              backdrop-blur-xl 
              border border-slate-200/50 dark:border-slate-700/50 
              rounded-2xl 
              shadow-lg dark:shadow-2xl
            ">
              <div className="p-4 sm:p-6 md:p-8 lg:p-12">
                {/* Dynamic HTML Content with Modern Styling */}
                <div 
                  className="
                    legal-content
                    max-w-[800px] mx-auto
                    
                    /* Base Typography - 16px body, 1.6 line-height */
                    text-base leading-[1.6]
                    
                    /* Prose Styling - Light Mode */
                    prose prose-slate prose-lg
                    
                    /* Headings - Space Grotesk font */
                    prose-h1:text-2xl prose-h1:sm:text-3xl prose-h1:font-bold 
                    prose-h1:text-slate-900 dark:prose-h1:text-white 
                    prose-h1:mb-6 prose-h1:mt-0
                    prose-h1:font-[Space_Grotesk]
                    
                    prose-h2:text-xl prose-h2:sm:text-2xl prose-h2:font-semibold 
                    prose-h2:text-slate-800 dark:prose-h2:text-slate-100 
                    prose-h2:mt-10 prose-h2:mb-4
                    prose-h2:pb-3 prose-h2:border-b prose-h2:border-slate-200 dark:prose-h2:border-slate-700
                    prose-h2:font-[Space_Grotesk]
                    
                    prose-h3:text-lg prose-h3:sm:text-xl prose-h3:font-medium 
                    prose-h3:text-slate-700 dark:prose-h3:text-slate-200 
                    prose-h3:mt-8 prose-h3:mb-3
                    prose-h3:font-[Space_Grotesk]
                    
                    /* Body Text - High contrast, readable */
                    prose-p:text-slate-600 dark:prose-p:text-slate-300 
                    prose-p:leading-[1.6] prose-p:mb-4
                    
                    /* Lists - Custom checkmark bullets */
                    prose-li:text-slate-600 dark:prose-li:text-slate-300 
                    prose-li:marker:text-primary dark:prose-li:marker:text-blue-400
                    prose-ul:my-4 prose-ol:my-4
                    prose-li:leading-[1.6]
                    
                    /* Strong & Links */
                    prose-strong:text-slate-900 dark:prose-strong:text-white 
                    prose-strong:font-semibold
                    
                    prose-a:text-primary dark:prose-a:text-blue-400 
                    prose-a:no-underline prose-a:font-medium
                    hover:prose-a:underline prose-a:transition-colors
                    
                    /* Blockquotes - Info boxes */
                    prose-blockquote:border-l-4 prose-blockquote:border-primary/50 dark:prose-blockquote:border-blue-500/50
                    prose-blockquote:bg-primary/5 dark:prose-blockquote:bg-blue-500/10
                    prose-blockquote:rounded-r-xl
                    prose-blockquote:pl-6 prose-blockquote:py-4 prose-blockquote:pr-4
                    prose-blockquote:not-italic
                    prose-blockquote:text-slate-700 dark:prose-blockquote:text-slate-300
                    
                    /* Code - Inline code styling */
                    prose-code:text-primary dark:prose-code:text-blue-300 
                    prose-code:bg-primary/5 dark:prose-code:bg-blue-500/10 
                    prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md
                    prose-code:font-normal prose-code:before:content-none prose-code:after:content-none
                    
                    /* Tables - Clean modern tables */
                    prose-table:border prose-table:border-slate-200 dark:prose-table:border-slate-700
                    prose-table:rounded-xl prose-table:overflow-hidden
                    prose-th:bg-slate-100 dark:prose-th:bg-slate-800 
                    prose-th:text-slate-900 dark:prose-th:text-white 
                    prose-th:font-semibold prose-th:text-left prose-th:px-4 prose-th:py-3
                    prose-td:border-t prose-td:border-slate-200 dark:prose-td:border-slate-700 
                    prose-td:text-slate-600 dark:prose-td:text-slate-300
                    prose-td:px-4 prose-td:py-3
                    
                    /* Custom Classes for Important Notices */
                    [&_.highlight]:bg-amber-100 dark:[&_.highlight]:bg-amber-500/20 
                    [&_.highlight]:text-amber-900 dark:[&_.highlight]:text-amber-200
                    [&_.highlight]:px-2 [&_.highlight]:py-0.5 [&_.highlight]:rounded-md
                    
                    [&_.fee-percentage]:font-bold [&_.fee-percentage]:text-primary dark:[&_.fee-percentage]:text-blue-400
                    
                    [&_.deadline]:font-bold [&_.deadline]:text-red-600 dark:[&_.deadline]:text-red-400
                    
                    [&_.important]:bg-amber-50 dark:[&_.important]:bg-amber-500/10
                    [&_.important]:border [&_.important]:border-amber-200 dark:[&_.important]:border-amber-500/30
                    [&_.important]:rounded-xl [&_.important]:p-4 [&_.important]:my-6
                    
                    [&_.info-box]:bg-blue-50 dark:[&_.info-box]:bg-blue-500/10
                    [&_.info-box]:border [&_.info-box]:border-blue-200 dark:[&_.info-box]:border-blue-500/30
                    [&_.info-box]:rounded-xl [&_.info-box]:p-4 [&_.info-box]:my-6
                    
                    /* Fee Tables - Accent styling */
                    [&_.fee-table]:bg-slate-50 dark:[&_.fee-table]:bg-slate-800/50
                    [&_.fee-table]:rounded-xl [&_.fee-table]:overflow-hidden
                    [&_.fee-table]:border [&_.fee-table]:border-slate-200 dark:[&_.fee-table]:border-slate-700
                    
                    /* Scroll margin for anchors */
                    [&_h2]:scroll-mt-28 [&_h3]:scroll-mt-28
                    
                    /* Max width for readability */
                    max-w-none
                  "
                  dangerouslySetInnerHTML={{ __html: processedContent }}
                />
              </div>
            </div>

            {/* Footer Navigation Cards */}
            <div className="mt-8 grid sm:grid-cols-2 gap-4">
              <a 
                href="/privacy-policy" 
                className="
                  group flex items-center gap-4 p-4
                  bg-white/70 dark:bg-slate-800/70 
                  backdrop-blur-xl 
                  border border-slate-200/50 dark:border-slate-700/50 
                  rounded-xl
                  hover:border-primary/30 dark:hover:border-primary/50
                  hover:shadow-lg
                  transition-all duration-200
                "
              >
                <div className="w-12 h-12 bg-primary/10 dark:bg-primary/20 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Shield className="h-6 w-6 text-primary dark:text-blue-400" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{language === 'fr' ? 'Lire notre' : 'Read our'}</p>
                  <p className="text-slate-900 dark:text-white font-medium">{language === 'fr' ? 'Politique de Confidentialité' : 'Privacy Policy'}</p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-400 dark:text-slate-500 group-hover:text-primary dark:group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
              </a>
              
              <a 
                href="/terms-of-service" 
                className="
                  group flex items-center gap-4 p-4
                  bg-white/70 dark:bg-slate-800/70 
                  backdrop-blur-xl 
                  border border-slate-200/50 dark:border-slate-700/50 
                  rounded-xl
                  hover:border-cyan-500/30 dark:hover:border-cyan-500/50
                  hover:shadow-lg
                  transition-all duration-200
                "
              >
                <div className="w-12 h-12 bg-cyan-500/10 dark:bg-cyan-500/20 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Scale className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{language === 'fr' ? 'Lire nos' : 'Read our'}</p>
                  <p className="text-slate-900 dark:text-white font-medium">{language === 'fr' ? 'Conditions d\'Utilisation' : 'Terms of Service'}</p>
                </div>
                <ChevronRight className="h-5 w-5 text-slate-400 dark:text-slate-500 group-hover:text-cyan-500 dark:group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
              </a>
            </div>
          </main>
        </div>
      </div>

      {/* Back to Top Button */}
      {showBackToTop && (
        <Button
          onClick={scrollToTop}
          className="
            fixed bottom-6 right-6 w-12 h-12 rounded-full 
            bg-primary hover:bg-primary/90 
            shadow-lg shadow-primary/25
            z-50
          "
          size="icon"
          data-testid="back-to-top"
        >
          <ChevronUp className="h-5 w-5" />
        </Button>
      )}
    </div>
  );
};

export default DynamicLegalPage;
