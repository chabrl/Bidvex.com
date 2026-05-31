"""
iter249 Mission 4 — Server-side HTML sanitizer.

Strips dangerous execution vectors from any broker/admin-supplied HTML
payload before it lands in the DB or the outbound SendGrid pipeline.

Defends against:
  • <script>, <iframe>, <object>, <embed> tag injection
  • `on*` event handler attributes (onclick, onerror, onload, …)
  • `javascript:` and `data:` URI schemes inside href/src
  • Inline `style="expression(...)"` IE-7 vectors
  • Malformed payloads that try to break out of attribute quoting

The canonical entry points are:
  • `sanitize_user_html(html)` — for full HTML payloads (email bodies,
     marketing content, broker descriptions).
  • `sanitize_inline(text)` — for short single-line strings (subjects,
     names) that should not contain ANY markup.
"""
from __future__ import annotations

from typing import Iterable, Optional

import bleach
from bleach.css_sanitizer import CSSSanitizer

# Conservative allow-list — covers all formatting needed by transactional
# emails + broker listing descriptions WITHOUT giving an XSS surface.
ALLOWED_TAGS: tuple[str, ...] = (
    "a", "abbr", "b", "blockquote", "br", "code", "div", "em", "h1",
    "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p",
    "pre", "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "u", "ul", "small",
)

ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "*": ["class", "id", "style", "title"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "table": ["border", "cellpadding", "cellspacing", "width", "align"],
    "td": ["colspan", "rowspan", "align", "valign", "width"],
    "th": ["colspan", "rowspan", "align", "valign", "width"],
}

# Whitelisted URL schemes for `href` / `src`. `data:` is explicitly
# rejected because it can carry arbitrary HTML/JS payloads inline.
ALLOWED_PROTOCOLS: tuple[str, ...] = ("http", "https", "mailto", "tel")

_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "background-color", "border", "border-radius", "color",
        "display", "font-family", "font-size", "font-weight",
        "height", "line-height", "margin", "padding", "text-align",
        "text-decoration", "width", "max-width", "min-width",
        "letter-spacing", "vertical-align",
    ],
)


def sanitize_user_html(
    html: Optional[str],
    *,
    extra_allowed_tags: Optional[Iterable[str]] = None,
) -> str:
    """Sanitize a full HTML payload supplied by a broker/admin.

    Returns an empty string for None/empty input so the caller can
    safely concatenate the result. Strips every dangerous construct
    (`<script>`, `on*=`, `javascript:`, …) while preserving the
    standard transactional formatting tags.
    """
    if not html:
        return ""
    tags = list(ALLOWED_TAGS)
    if extra_allowed_tags:
        tags = tags + [t for t in extra_allowed_tags if t not in tags]
    cleaned = bleach.clean(
        html,
        tags=tags,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,           # remove disallowed tags entirely
        strip_comments=True,  # drop <!-- … --> blocks
    )
    return cleaned


def sanitize_inline(text: Optional[str]) -> str:
    """Strip ALL markup from a short string (email subjects, names, …).

    Use for fields that must never carry tags — render-safe text only.
    """
    if not text:
        return ""
    return bleach.clean(text, tags=[], strip=True).strip()


__all__ = [
    "ALLOWED_TAGS",
    "ALLOWED_ATTRIBUTES",
    "ALLOWED_PROTOCOLS",
    "sanitize_user_html",
    "sanitize_inline",
]
