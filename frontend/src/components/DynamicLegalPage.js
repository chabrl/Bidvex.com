/**
 * DynamicLegalPage - Modern Legal Page Component
 * Features glassmorphism design and sticky navigation sidebar
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Loader2, ChevronRight, FileText, Shield, Scale, 
  BookOpen, AlertCircle, Clock, ChevronUp
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Section icons mapping
const SECTION_ICONS = {
  'information': FileText,
  'privacy': Shield,
  'terms': Scale,
  'rights': BookOpen,
  'liability': AlertCircle,
  'default': FileText
};

const DynamicLegalPage = ({ pageKey, fallbackTitle, fallbackContent }) => {
  const { i18n } = useTranslation();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSection, setActiveSection] = useState('');
  const [showBackToTop, setShowBackToTop] = useState(false);
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
      if (lowerText.includes('information') || lowerText.includes('collect')) iconKey = 'information';
      else if (lowerText.includes('privacy') || lowerText.includes('data')) iconKey = 'privacy';
      else if (lowerText.includes('terms') || lowerText.includes('condition')) iconKey = 'terms';
      else if (lowerText.includes('rights') || lowerText.includes('user')) iconKey = 'rights';
      else if (lowerText.includes('liability') || lowerText.includes('warranty')) iconKey = 'liability';
      
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
      const scrollPosition = window.scrollY + 100;
      
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
      const offset = 80; // Account for sticky header
      const elementPosition = element.offsetTop - offset;
      window.scrollTo({ top: elementPosition, behavior: 'smooth' });
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-blue-400 mx-auto mb-4" />
          <p className="text-slate-400">Loading content...</p>
        </div>
      </div>
    );
  }

  if (error && !content) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <Card className="max-w-lg bg-white/10 backdrop-blur-xl border-white/20">
          <CardContent className="pt-6">
            <p className="text-red-400 mb-4">Failed to load content: {error}</p>
            <p className="text-sm text-slate-400">
              Please try refreshing the page or contact support if the problem persists.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" data-testid="legal-page">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-50" />
        
        {/* Gradient Orbs */}
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
        <div className="absolute top-20 right-1/4 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl" />
        
        <div className="relative container mx-auto px-4 py-16 sm:py-24">
          <div className="max-w-3xl mx-auto text-center">
            <Badge className="mb-4 bg-white/10 text-white border-white/20 backdrop-blur-sm">
              <FileText className="h-3 w-3 mr-1" />
              Legal Document
            </Badge>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white mb-6 tracking-tight">
              {content?.title || fallbackTitle}
            </h1>
            <p className="text-lg text-slate-300 max-w-2xl mx-auto">
              Please read these terms carefully. By using our platform, you agree to be bound by these terms.
            </p>
            
            {/* Last Updated */}
            <div className="mt-6 inline-flex items-center gap-2 text-sm text-slate-400">
              <Clock className="h-4 w-4" />
              Last updated: {new Date().toLocaleDateString(language === 'fr' ? 'fr-FR' : 'en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content with Sidebar */}
      <div className="container mx-auto px-4 pb-16">
        <div className="flex flex-col lg:flex-row gap-8 max-w-7xl mx-auto">
          
          {/* Sticky Sidebar Navigation */}
          {sections.length > 0 && (
            <aside className="lg:w-72 flex-shrink-0">
              <div className="lg:sticky lg:top-24">
                <Card className="bg-white/5 backdrop-blur-xl border-white/10 shadow-2xl overflow-hidden">
                  <CardContent className="p-0">
                    <div className="p-4 border-b border-white/10">
                      <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
                        Contents
                      </h3>
                    </div>
                    <nav className="p-2 max-h-[60vh] overflow-y-auto">
                      {sections.map((section) => {
                        const Icon = SECTION_ICONS[section.iconKey] || FileText;
                        const isActive = activeSection === section.id;
                        
                        return (
                          <button
                            key={section.id}
                            onClick={() => scrollToSection(section.id)}
                            className={`
                              w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-all duration-200
                              flex items-center gap-2 group
                              ${section.level === 3 ? 'ml-4' : ''}
                              ${isActive 
                                ? 'bg-blue-500/20 text-blue-300 border-l-2 border-blue-400' 
                                : 'text-slate-400 hover:text-white hover:bg-white/5'
                              }
                            `}
                            data-testid={`nav-${section.id}`}
                          >
                            <Icon className={`h-4 w-4 flex-shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                            <span className="text-sm truncate">{section.text}</span>
                            <ChevronRight className={`h-3 w-3 ml-auto flex-shrink-0 transition-transform ${isActive ? 'rotate-90' : ''}`} />
                          </button>
                        );
                      })}
                    </nav>
                  </CardContent>
                </Card>
              </div>
            </aside>
          )}

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            <Card className="bg-white/5 backdrop-blur-xl border-white/10 shadow-2xl">
              <CardContent className="p-6 sm:p-8 lg:p-12">
                {/* Dynamic HTML Content with Modern Styling */}
                <div 
                  className="
                    prose prose-lg prose-invert max-w-none
                    
                    /* Headings */
                    prose-h1:text-3xl prose-h1:font-bold prose-h1:text-white prose-h1:mb-6 prose-h1:mt-0
                    prose-h2:text-2xl prose-h2:font-semibold prose-h2:text-white prose-h2:mt-12 prose-h2:mb-4
                    prose-h2:pb-3 prose-h2:border-b prose-h2:border-white/10
                    prose-h3:text-xl prose-h3:font-medium prose-h3:text-slate-200 prose-h3:mt-8 prose-h3:mb-3
                    
                    /* Body Text */
                    prose-p:text-slate-300 prose-p:leading-relaxed prose-p:mb-4
                    
                    /* Lists */
                    prose-li:text-slate-300 prose-li:marker:text-blue-400
                    prose-ul:my-4 prose-ol:my-4
                    
                    /* Strong & Links */
                    prose-strong:text-white prose-strong:font-semibold
                    prose-a:text-blue-400 prose-a:no-underline hover:prose-a:text-blue-300 prose-a:transition-colors
                    
                    /* Blockquotes */
                    prose-blockquote:border-l-4 prose-blockquote:border-blue-500/50
                    prose-blockquote:bg-white/5 prose-blockquote:rounded-r-lg
                    prose-blockquote:pl-6 prose-blockquote:py-4 prose-blockquote:italic
                    prose-blockquote:text-slate-300
                    
                    /* Code */
                    prose-code:text-blue-300 prose-code:bg-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
                    
                    /* Tables */
                    prose-table:border prose-table:border-white/10
                    prose-th:bg-white/5 prose-th:text-white prose-th:font-semibold
                    prose-td:border-t prose-td:border-white/10 prose-td:text-slate-300
                    
                    /* Custom Highlights */
                    [&_.highlight]:bg-yellow-500/20 [&_.highlight]:px-1.5 [&_.highlight]:py-0.5 [&_.highlight]:rounded
                    [&_.fee-percentage]:font-bold [&_.fee-percentage]:text-blue-400
                    [&_.deadline]:font-bold [&_.deadline]:text-red-400
                    
                    /* Scroll margin for anchors */
                    [&_h2]:scroll-mt-24 [&_h3]:scroll-mt-24
                  "
                  dangerouslySetInnerHTML={{ __html: processedContent }}
                />
              </CardContent>
            </Card>

            {/* Footer Navigation */}
            <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-between">
              <Card className="bg-white/5 backdrop-blur-xl border-white/10 p-4 flex-1 hover:bg-white/10 transition-colors cursor-pointer">
                <a href="/privacy-policy" className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                    <Shield className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Read our</p>
                    <p className="text-white font-medium">Privacy Policy</p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-slate-400 ml-auto" />
                </a>
              </Card>
              <Card className="bg-white/5 backdrop-blur-xl border-white/10 p-4 flex-1 hover:bg-white/10 transition-colors cursor-pointer">
                <a href="/terms-of-service" className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
                    <Scale className="h-5 w-5 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Read our</p>
                    <p className="text-white font-medium">Terms of Service</p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-slate-400 ml-auto" />
                </a>
              </Card>
            </div>
          </main>
        </div>
      </div>

      {/* Back to Top Button */}
      {showBackToTop && (
        <Button
          onClick={scrollToTop}
          className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 shadow-lg z-50"
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
