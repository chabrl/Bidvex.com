/**
 * BidVex Blogs — SEO landing page.
 *
 * iter331: Migrated from static array → DB-driven via GET /api/blogs/articles.
 * Renders gracefully when DB is empty (static intro stays, grid hidden).
 *
 * Each article links to /blogs/:slug → BlogArticlePage which fetches
 * GET /api/blogs/articles/:slug and renders the body Markdown.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';

import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import {
  Newspaper, ArrowRight, BookOpen, Gavel, ShieldCheck, Truck,
  Warehouse, Sparkles, FileText, Loader2,
} from 'lucide-react';
import API_BASE from '../config';
import { LangLink } from '../components/LangLink';

const ICON_MAP = {
  Gavel,
  ShieldCheck,
  Warehouse,
  Truck,
  Sparkles,
  BookOpen,
  Newspaper,
  FileText,
};

const TAG_LABELS = {
  platform:   { en: 'Platform',   fr: 'Plateforme' },
  compliance: { en: 'Compliance', fr: 'Conformité' },
  storage:    { en: 'Storage',    fr: 'Entreposage' },
  vehicles:   { en: 'Vehicles',   fr: 'Véhicules' },
  partners:   { en: 'Partners',   fr: 'Partenaires' },
  security:   { en: 'Security',   fr: 'Sécurité' },
  marketing:  { en: 'Marketing',  fr: 'Marketing' },
  company:    { en: 'Company',    fr: 'Entreprise' },
  product:    { en: 'Product',    fr: 'Produit' },
};

export default function BlogsPage() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/blogs/articles`);
        if (!cancelled) setArticles(r.data?.articles || []);
      } catch (e) {
        if (!cancelled) setArticles([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50" data-testid="blogs-page">
      <Helmet>
        <title>{fr ? 'Blog BidVex — Articles, guides et nouveautés' : 'BidVex Blog — Articles, Guides & Platform Insights'}</title>
        <meta
          name="description"
          content={fr
            ? 'Articles, guides et explications techniques pour vendeurs, courtiers, concessionnaires et acheteurs sur la plateforme d\'enchères BidVex.'
            : 'Articles, guides, and technical explanations for sellers, brokers, dealers, and buyers on the BidVex auction platform.'}
        />
        <link rel="canonical" href="https://bidvex.com/blogs" />
      </Helmet>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-slate-200" style={{ background: 'linear-gradient(135deg, #0B2545 0%, #1B3D6F 60%, #2186C6 100%)' }}>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-16 md:py-20 text-white">
          <div className="flex items-center gap-2 text-xs sm:text-sm uppercase tracking-[0.2em] text-cyan-200 mb-4" data-testid="blogs-eyebrow">
            <Newspaper className="w-4 h-4" />
            <span>{fr ? 'Salle de presse & Blog' : 'Press Room & Blog'}</span>
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-tight mb-4" data-testid="blogs-hero-title">
            {fr ? 'Articles, guides et nouveautés BidVex' : 'BidVex Articles, Guides & Platform Insights'}
          </h1>
          <p className="text-base sm:text-lg text-cyan-100 max-w-3xl">
            {fr
              ? 'Le dépôt centralisé de définitions opérationnelles, conseils pratiques et explications techniques pour faire grandir la communauté BidVex.'
              : 'The centralized repository of operational definitions, user hints, and technical explanations powering the BidVex community.'}
          </p>
          <p className="text-xs sm:text-sm text-cyan-200 mt-6">
            {fr ? 'Vous représentez la presse ou les médias ? Écrivez à ' : 'Press or media inquiries? Email '}
            <a href="mailto:service@bidvex.com" className="underline hover:text-white" data-testid="blogs-press-email">service@bidvex.com</a>
            {fr ? ' — nous répondons sous 24 h ouvrables.' : ' — we respond within 1 business day.'}
          </p>
        </div>
      </section>

      {/* Article grid */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-12 md:py-16">
        {loading ? (
          <div className="flex items-center justify-center py-16" data-testid="blogs-loading">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-2" />
            <span className="text-slate-600">{fr ? 'Chargement…' : 'Loading…'}</span>
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-12 text-slate-500" data-testid="blogs-empty">
            <BookOpen className="w-10 h-10 mx-auto mb-3 text-slate-400" />
            <p>{fr ? 'Aucun article publié pour l\'instant. Revenez bientôt !' : 'No published articles yet. Check back soon!'}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6" data-testid="blogs-grid">
            {articles.map((a) => {
              const Icon = ICON_MAP[a.icon] || BookOpen;
              const tagLabel = (TAG_LABELS[a.tag] || {})[fr ? 'fr' : 'en'] || a.tag;
              return (
                <LangLink
                  key={a.id || a.slug}
                  to={`/blogs/${a.slug}`}
                  data-testid={`blogs-article-${a.slug}`}
                  className="group bg-white rounded-xl border border-slate-200 hover:border-cyan-400 hover:shadow-xl transition-all duration-300 overflow-hidden flex flex-col"
                >
                  {a.cover_url && (
                    <div className="aspect-[16/9] overflow-hidden bg-slate-100">
                      <img
                        src={a.cover_url}
                        alt={fr ? a.title_fr : a.title_en}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        loading="lazy"
                      />
                    </div>
                  )}
                  <div className="px-5 sm:px-6 pt-5 sm:pt-6 flex items-start justify-between">
                    <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg flex items-center justify-center" style={{ background: '#F0F8FF' }}>
                      <Icon className="w-5 h-5 sm:w-6 sm:h-6" style={{ color: '#2186C6' }} />
                    </div>
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-cyan-700 bg-cyan-50 px-2 py-1 rounded-full">
                      {tagLabel}
                    </span>
                  </div>
                  <div className="px-5 sm:px-6 pt-4 pb-5 sm:pb-6 flex-1 flex flex-col">
                    <h2 className="text-base sm:text-lg font-bold text-slate-900 mb-2 leading-snug group-hover:text-cyan-700 transition-colors">
                      {fr ? a.title_fr : a.title_en}
                    </h2>
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed flex-1">
                      {fr ? a.excerpt_fr : a.excerpt_en}
                    </p>
                    <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="text-slate-500">
                        {a.read_min || 5} {fr ? 'min de lecture' : 'min read'}
                      </span>
                      <span className="inline-flex items-center gap-1 text-cyan-700 font-semibold group-hover:gap-2 transition-all">
                        {fr ? 'Lire la suite' : 'Read more'}
                        <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                </LangLink>
              );
            })}
          </div>
        )}

        {/* CTA */}
        <div className="mt-12 sm:mt-16 rounded-2xl p-6 sm:p-8 md:p-12 text-center" style={{ background: '#0B2545', color: 'white' }} data-testid="blogs-cta-card">
          <BookOpen className="w-10 h-10 mx-auto mb-3 text-cyan-300" />
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold mb-3">
            {fr ? 'Un sujet à creuser ? Suggérez un article.' : 'Have a topic you\'d like us to cover?'}
          </h2>
          <p className="text-sm sm:text-base text-cyan-100 max-w-xl mx-auto mb-6">
            {fr
              ? 'Notre équipe éditoriale publie chaque semaine. Soumettez vos idées et nous y répondrons par un article ou un guide.'
              : 'Our editorial team publishes weekly. Submit topic ideas and we\'ll respond with an article or how-to guide.'}
          </p>
          <LangLink
            to="/contact-us"
            data-testid="blogs-suggest-topic-link"
            className="inline-flex items-center gap-2 px-5 sm:px-6 py-3 bg-cyan-400 text-slate-900 font-semibold rounded-lg hover:bg-cyan-300 transition-colors"
          >
            {fr ? 'Proposer un sujet' : 'Suggest a Topic'}
            <ArrowRight className="w-4 h-4" />
          </LangLink>
        </div>
      </section>
    </div>
  );
}
