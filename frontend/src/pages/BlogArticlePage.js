/**
 * iter331 — BlogArticlePage
 *
 * Public article detail page rendered at /blogs/:slug. Fetches
 * GET /api/blogs/articles/:slug and renders the Markdown body in the
 * user's preferred language (EN/FR). Falls back to 404 on missing slug.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, Loader2, Newspaper, Calendar } from 'lucide-react';
import API_BASE from '../config';

function renderMarkdown(text) {
  if (!text) return null;
  const lines = String(text).split(/\r?\n/);
  const blocks = [];
  let listBuf = null;

  const flushList = () => {
    if (listBuf && listBuf.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc list-inside space-y-1 my-3 text-base text-slate-700">
          {listBuf.map((item, i) => (<li key={i}>{renderInline(item)}</li>))}
        </ul>,
      );
    }
    listBuf = null;
  };

  const renderInline = (s) => {
    const parts = [];
    let rest = s;
    let key = 0;
    const re = /(\*\*[^*]+\*\*|`[^`]+`)/;
    while (rest) {
      const m = rest.match(re);
      if (!m) { parts.push(rest); break; }
      const idx = m.index;
      if (idx > 0) parts.push(rest.slice(0, idx));
      const tok = m[0];
      if (tok.startsWith('**')) parts.push(<strong key={`b-${key++}`}>{tok.slice(2, -2)}</strong>);
      else if (tok.startsWith('`')) parts.push(<code key={`c-${key++}`} className="px-1 py-0.5 bg-slate-100 rounded text-sm">{tok.slice(1, -1)}</code>);
      rest = rest.slice(idx + tok.length);
    }
    return parts;
  };

  lines.forEach((rawLine, i) => {
    const line = rawLine.trimEnd();
    if (line.startsWith('### ')) {
      flushList();
      blocks.push(<h4 key={`h3-${i}`} className="text-lg sm:text-xl font-semibold mt-5 mb-2 text-slate-900">{renderInline(line.slice(4))}</h4>);
    } else if (line.startsWith('## ')) {
      flushList();
      blocks.push(<h3 key={`h2-${i}`} className="text-xl sm:text-2xl font-bold mt-6 mb-2 text-slate-900">{renderInline(line.slice(3))}</h3>);
    } else if (line.startsWith('# ')) {
      flushList();
      blocks.push(<h2 key={`h1-${i}`} className="text-2xl sm:text-3xl font-bold mt-7 mb-3 text-slate-900">{renderInline(line.slice(2))}</h2>);
    } else if (line.startsWith('- ')) {
      if (!listBuf) listBuf = [];
      listBuf.push(line.slice(2));
    } else if (line === '') {
      flushList();
    } else {
      flushList();
      blocks.push(<p key={`p-${i}`} className="text-base leading-relaxed my-3 text-slate-700">{renderInline(line)}</p>);
    }
  });
  flushList();
  return blocks;
}

export default function BlogArticlePage() {
  const { slug } = useParams();
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/blogs/articles/${slug}`);
        if (!cancelled) setArticle(r.data);
      } catch (e) {
        if (cancelled) return;
        if (e?.response?.status === 404) setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="blog-article-loading">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-3" />
        <span>{fr ? 'Chargement…' : 'Loading…'}</span>
      </div>
    );
  }

  if (notFound || !article) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center py-20 px-4" data-testid="blog-article-not-found">
        <div className="max-w-md text-center">
          <Newspaper className="w-12 h-12 mx-auto mb-4 text-slate-400" />
          <h1 className="text-2xl font-bold mb-2">{fr ? 'Article introuvable' : 'Article not found'}</h1>
          <p className="text-slate-600 mb-6">
            {fr
              ? 'L\'article que vous cherchez n\'existe pas ou a été retiré.'
              : 'The article you\'re looking for doesn\'t exist or was unpublished.'}
          </p>
          <Link
            to="/blogs"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700"
            data-testid="back-to-blogs-link"
          >
            <ChevronLeft className="w-4 h-4" />
            {fr ? 'Retour au blog' : 'Back to blog'}
          </Link>
        </div>
      </div>
    );
  }

  const title = fr ? article.title_fr : article.title_en;
  const body = fr ? article.body_fr : article.body_en;
  const excerpt = fr ? article.excerpt_fr : article.excerpt_en;
  const publishedAt = article.published_at ? new Date(article.published_at) : null;

  return (
    <div className="min-h-screen bg-white" data-testid="blog-article-page">
      <Helmet>
        <title>{`${title} — BidVex Blog`}</title>
        <meta name="description" content={excerpt} />
        <link rel="canonical" href={`https://bidvex.com/blogs/${article.slug}`} />
      </Helmet>

      {/* Hero */}
      <section
        className="border-b border-slate-200 px-4 sm:px-6 py-10 sm:py-14"
        style={{ background: 'linear-gradient(135deg, #0B2545 0%, #1B3D6F 60%, #2186C6 100%)' }}
      >
        <div className="max-w-3xl mx-auto text-white">
          <Link
            to="/blogs"
            className="inline-flex items-center gap-1 text-sm text-cyan-200 hover:text-white mb-4"
            data-testid="article-back-link"
          >
            <ChevronLeft className="w-4 h-4" />
            {fr ? 'Retour au blog' : 'Back to blog'}
          </Link>
          <h1
            className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold leading-tight mb-3"
            data-testid="article-title"
          >
            {title}
          </h1>
          <p className="text-sm sm:text-base text-cyan-100">{excerpt}</p>
          <div className="flex flex-wrap items-center gap-3 mt-4 text-xs text-cyan-200">
            {publishedAt && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {publishedAt.toLocaleDateString(fr ? 'fr-CA' : 'en-CA', { year: 'numeric', month: 'long', day: 'numeric' })}
              </span>
            )}
            <span>{article.read_min || 5} {fr ? 'min de lecture' : 'min read'}</span>
          </div>
        </div>
      </section>

      {/* Cover image */}
      {article.cover_url && (
        <div className="max-w-3xl mx-auto px-4 sm:px-6 -mt-6 sm:-mt-8">
          <img
            src={article.cover_url}
            alt={title}
            className="w-full rounded-xl shadow-xl"
            loading="lazy"
            data-testid="article-cover-image"
          />
        </div>
      )}

      {/* Body */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <article data-testid="article-body" className="prose-like">
          {renderMarkdown(body)}
        </article>
      </section>
    </div>
  );
}
