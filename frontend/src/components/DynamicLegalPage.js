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
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white dark:from-slate-900 dark:to-slate-800 py-12">
      <div className="container mx-auto px-4 max-w-4xl">
        <Card className="shadow-lg border-2 border-slate-200 dark:border-slate-700">
          <CardContent className="p-8 md:p-12">
            {/* Title - High Contrast */}
            <h1 className="text-4xl font-bold mb-6 text-slate-900 dark:text-white">
              {content?.title || fallbackTitle}
            </h1>

            {/* Dynamic HTML Content - High Contrast Styling */}
            <div 
              className="prose prose-lg max-w-none 
                prose-headings:text-slate-900 dark:prose-headings:text-white
                prose-h1:text-slate-900 dark:prose-h1:text-white
                prose-h2:text-slate-900 dark:prose-h2:text-white
                prose-h3:text-slate-800 dark:prose-h3:text-slate-100
                prose-p:text-slate-700 dark:prose-p:text-slate-300
                prose-li:text-slate-700 dark:prose-li:text-slate-300
                prose-strong:text-slate-900 dark:prose-strong:text-white prose-strong:font-bold
                prose-a:text-blue-600 dark:prose-a:text-blue-400
                [&_strong]:font-bold [&_strong]:text-slate-900 dark:[&_strong]:text-white
                [&_.highlight]:bg-yellow-100 dark:[&_.highlight]:bg-yellow-900/30 [&_.highlight]:px-1 [&_.highlight]:rounded
                [&_.fee-percentage]:font-bold [&_.fee-percentage]:text-blue-700 dark:[&_.fee-percentage]:text-blue-400
                [&_.deadline]:font-bold [&_.deadline]:text-red-700 dark:[&_.deadline]:text-red-400"
              dangerouslySetInnerHTML={{ __html: content?.content || fallbackContent }}
            />

            {/* Timestamp */}
            <div className="mt-12 pt-6 border-t border-slate-200 dark:border-slate-700">
              <p className="text-sm text-slate-600 dark:text-slate-400">
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
