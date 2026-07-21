/**
 * iter369 — Sanitized HTML renderer.
 *
 * Renders trusted (but user-authored) HTML content — auction terms, seller
 * descriptions — after passing it through DOMPurify. NEVER exposes raw
 * `<h3>` / `<ul>` etc. tags as visible text, and NEVER opens the page to
 * script injection.
 *
 * Applies Tailwind `prose` class by default so headings, lists, tables,
 * and paragraphs get sensible typography without any extra CSS.
 */
import React, { useMemo } from 'react';
import DOMPurify from 'dompurify';

const DEFAULT_ALLOWED_TAGS = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins', 'mark',
  'ul', 'ol', 'li',
  'blockquote', 'code', 'pre',
  'a', 'span', 'div',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'hr',
];

const DEFAULT_ALLOWED_ATTRS = ['href', 'title', 'target', 'rel', 'class', 'colspan', 'rowspan'];

export default function SanitizedHtml({ html, className = '', allowLinks = true }) {
  const clean = useMemo(() => {
    if (!html || typeof html !== 'string') return '';
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: DEFAULT_ALLOWED_TAGS,
      ALLOWED_ATTR: allowLinks ? DEFAULT_ALLOWED_ATTRS : DEFAULT_ALLOWED_ATTRS.filter((a) => a !== 'href'),
      // Force target="_blank" links to be safe (see afterSanitizeAttributes).
      ADD_ATTR: ['target', 'rel'],
    });
  }, [html, allowLinks]);

  if (!clean) return null;
  return (
    <div
      className={className || 'prose prose-sm dark:prose-invert max-w-none'}
      data-testid="sanitized-html"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  );
}
