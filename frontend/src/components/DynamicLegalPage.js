import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DynamicLegalPage = ({ pageKey, fallbackTitle, fallbackContent }) => {
  const { i18n } = useTranslation();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const language = i18n.language || 'en';

  useEffect(() => {
    fetchContent();
  }, [language, pageKey]);

  const fetchContent = async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('[DynamicLegalPage] Fetching content:', { pageKey, language });
      
      const response = await axios.get(
        `${API}/site-config/legal-pages?language=${language}`
      );

      console.log('[DynamicLegalPage] Response:', response.data);

      if (response.data.success && response.data.pages[pageKey]) {
        setContent(response.data.pages[pageKey]);
      } else {
        // Fallback to default content if page not found
        setContent({
          title: fallbackTitle,
          content: fallbackContent,
          link_type: 'page'
        });
      }
    } catch (err) {
      console.error('[DynamicLegalPage] Error fetching content:', err);
      setError(err.message);
      
      // Fallback to default content on error
      setContent({
        title: fallbackTitle,
        content: fallbackContent,
        link_type: 'page'
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading content...</p>
        </div>
      </div>
    );
  }

  if (error && !content) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white">
        <Card className="max-w-lg">
          <CardContent className="pt-6">
            <p className="text-red-500 mb-4">Failed to load content: {error}</p>
            <p className="text-sm text-muted-foreground">
              Please try refreshing the page or contact support if the problem persists.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-12">
      <div className="container mx-auto px-4 max-w-4xl">
        <Card className="shadow-lg">
          <CardContent className="p-8 md:p-12">
            {/* Title */}
            <h1 className="text-4xl font-bold mb-6 text-gray-900">
              {content?.title || fallbackTitle}
            </h1>

            {/* Dynamic HTML Content */}
            <div 
              className="prose prose-lg max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-a:text-blue-600 prose-strong:text-gray-900"
              dangerouslySetInnerHTML={{ __html: content?.content || fallbackContent }}
            />

            {/* Timestamp */}
            <div className="mt-12 pt-6 border-t border-gray-200">
              <p className="text-sm text-muted-foreground">
                Last updated: {new Date().toLocaleDateString(language === 'fr' ? 'fr-FR' : 'en-US')}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DynamicLegalPage;
