#!/usr/bin/env python3
"""Build the blog: markdown in `content/`, static HTML out in `dist/`.

Usage:
    ./build              build the site
    ./build --drafts     include posts marked `Draft: true`
    ./build --serve      build, then serve dist/ at http://localhost:8000
    ./build --zip        build, then package dist/ into site.zip
    ./build --check      check every palette's colour contrast (no build)
"""

from __future__ import annotations

import hashlib
import html
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import SimpleTagInlineProcessor
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).parent.resolve()
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
TEMPLATES = ROOT / "templates"
DIST = ROOT / "dist"
PALETTES_FILE = ROOT / "palettes.toml"

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y")

COLOR_ROLES = (
    "bg", "surface", "text", "muted", "border",
    "title", "h1", "h2", "h3", "bold", "italic",
    "mark_bg", "mark_text", "link",
)


# ─────────────────────────────────────────────────────────────
# Markdown: ==highlight== support
# ─────────────────────────────────────────────────────────────

class HighlightExtension(Extension):
    """Renders ==text== as <mark>text</mark>."""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            SimpleTagInlineProcessor(r"(==)(.+?)==", "mark"), "highlight", 175
        )


class StrikethroughExtension(Extension):
    """Renders ~~text~~ as <del>text</del>."""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            SimpleTagInlineProcessor(r"(~~)(.+?)~~", "del"), "strikethrough", 174
        )


def make_markdown() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=[
            "extra",          # tables, fenced code, footnotes, attr_list, def_list
            "meta",           # frontmatter
            "sane_lists",
            "smarty",         # curly quotes and proper dashes
            "toc",
            "codehilite",
            HighlightExtension(),
            StrikethroughExtension(),
        ],
        extension_configs={
            "codehilite": {"guess_lang": False, "css_class": "codehilite"},
            "toc": {"permalink": False},
        },
    )


# ─────────────────────────────────────────────────────────────
# Content model
# ─────────────────────────────────────────────────────────────

@dataclass
class Doc:
    slug: str
    title: str
    body: str                      # rendered HTML
    url: str                       # relative to site root, e.g. "posts/foo/"
    date: date | None = None
    summary: str = ""
    draft: bool = False
    words: int = 0
    nav_hidden: bool = False
    meta: dict = field(default_factory=dict)
    toc_tokens: list = field(default_factory=list)
    folder: str = ""               # "" for loose posts, else the folder name (e.g. "c")

    @property
    def folder_label(self) -> str:
        """Human-readable folder name for the sidebar (e.g. "c" → "C")."""
        return self.folder.replace("-", " ").replace("_", " ").title()

    @property
    def depth(self) -> int:
        """How many directories deep the output file sits."""
        return len([p for p in self.url.split("/") if p])

    @property
    def root_prefix(self) -> str:
        return "../" * self.depth

    @property
    def date_display(self) -> str:
        return self.date.strftime("%d %B %Y") if self.date else ""

    @property
    def date_iso(self) -> str:
        return self.date.isoformat() if self.date else ""


def first_meta(meta: dict, key: str, default: str = "") -> str:
    values = meta.get(key)
    return values[0].strip() if values else default


def parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    print(f"  ! could not parse date {raw!r} — expected YYYY-MM-DD")
    return None


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-") or "untitled"


# ─────────────────────────────────────────────────────────────
# HTML post-processing
# ─────────────────────────────────────────────────────────────

def rewrite_asset_paths(body: str, root_prefix: str) -> str:
    """Make `assets/...` references work from any directory depth.

    Posts always write `assets/images/cat.jpg` (or `/assets/images/cat.jpg`);
    this rewrites them relative to the page being generated so the site works
    from a file:// path, a domain root, or a GitHub Pages subpath alike.
    """
    def repl(match: re.Match) -> str:
        attr, path = match.group(1), match.group(2)
        return f'{attr}="{root_prefix}{path.lstrip("/")}"'

    return re.sub(r'\b(src|href)="(/?assets/[^"]*)"', repl, body)


def mark_downloads(body: str) -> str:
    """Give links to downloadable files a class and a `download` attribute."""
    exts = r"pdf|zip|docx?|xlsx?|pptx?|csv|epub"

    def repl(match: re.Match) -> str:
        tag = match.group(0)
        if "download" in tag:
            return tag
        return tag[:-1] + ' download class="download-link">'

    return re.sub(rf'<a href="[^"]*\.({exts})"[^>]*>', repl, body, flags=re.I)


def wrap_figures(body: str) -> str:
    """Turn a paragraph holding a lone image into a <figure>.

    A markdown title becomes the caption:  ![alt](path "the caption")
    """
    pattern = re.compile(r"<p>(<img\b[^>]*/?>)</p>")

    def repl(match: re.Match) -> str:
        img = match.group(1)
        caption_match = re.search(r'title="([^"]*)"', img)
        if caption_match and caption_match.group(1):
            caption = caption_match.group(1)
            img = img.replace(f' title="{caption}"', "")
            return f"<figure>{img}<figcaption>{caption}</figcaption></figure>"
        return f"<figure>{img}</figure>"

    return pattern.sub(repl, body)


def lazy_load_images(body: str) -> str:
    return re.sub(r"<img\b(?![^>]*loading=)", '<img loading="lazy" decoding="async"', body)


def external_links(body: str) -> str:
    """Open off-site links in a new tab."""
    def repl(match: re.Match) -> str:
        tag = match.group(0)
        if "target=" in tag:
            return tag
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer">'

    return re.sub(r'<a href="https?://[^"]*"[^>]*>', repl, body)


def task_lists(body: str) -> str:
    """Turn `- [ ]` and `- [x]` list items into real (read-only) checkboxes."""
    def repl(match: re.Match) -> str:
        opening_p = match.group(1) or ""
        checked = " checked" if match.group(2).lower() == "x" else ""
        return f'<li class="task-item">{opening_p}<input type="checkbox" disabled{checked}> '

    return re.sub(r"<li>(<p>)?\[([ xX])\]\s+", repl, body)


def process_body(body: str, root_prefix: str) -> str:
    body = task_lists(body)
    body = wrap_figures(body)
    body = mark_downloads(body)
    body = external_links(body)
    body = lazy_load_images(body)
    return rewrite_asset_paths(body, root_prefix)


def summarize(body: str, limit: int = 200) -> str:
    """First paragraph of a post, stripped to plain text."""
    match = re.search(r"<p>(.*?)</p>", body, re.S)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", "", match.group(1))
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


# ─────────────────────────────────────────────────────────────
# Loading content
# ─────────────────────────────────────────────────────────────

def load_doc(path: Path, md: markdown.Markdown, url_prefix: str, folder: str = "") -> Doc:
    md.reset()
    raw = path.read_text(encoding="utf-8")
    rendered = md.convert(raw)
    meta = getattr(md, "Meta", {}) or {}

    slug = first_meta(meta, "slug") or slugify(path.stem)
    url = f"{url_prefix}{slug}/" if url_prefix else f"{slug}/"
    title = first_meta(meta, "title") or slug.replace("-", " ").title()

    doc = Doc(
        slug=slug,
        title=title,
        body="",  # filled below, once we know the depth
        url=url,
        date=parse_date(first_meta(meta, "date")),
        draft=first_meta(meta, "draft").lower() in ("true", "yes", "1"),
        nav_hidden=first_meta(meta, "nav").lower() in ("false", "no", "hide"),
        words=len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", rendered))),
        meta=meta,
        folder=folder,
    )
    doc.body = process_body(rendered, doc.root_prefix)
    doc.summary = first_meta(meta, "summary") or summarize(doc.body)
    # The `toc` extension fills this during convert; used to build the
    # per-article table of contents in the right rail.
    doc.toc_tokens = getattr(md, "toc_tokens", []) or []

    if doc.date is None:
        doc.date = date.fromtimestamp(path.stat().st_mtime)
    return doc


def load_all(include_drafts: bool) -> tuple[list[Doc], list[Doc]]:
    md = make_markdown()

    # (path, folder, url_prefix) for every post: loose ones directly in
    # content/posts/, plus one level of folders (content/posts/<folder>/*.md).
    post_sources = [(p, "", "posts/") for p in (CONTENT / "posts").glob("*.md")]
    for path in (CONTENT / "posts").glob("*/*.md"):
        folder = path.parent.name
        if folder.startswith("."):        # skip .obsidian and other hidden dirs
            continue
        post_sources.append((path, folder, f"posts/{folder}/"))

    # Only one level of nesting is supported — warn about anything deeper.
    for path in (CONTENT / "posts").glob("*/*/*.md"):
        if not any(part.startswith(".") for part in path.relative_to(CONTENT / "posts").parts):
            print(f"  ! ignoring {path.relative_to(CONTENT)} — folders can't be nested "
                  "more than one level deep")

    posts = []
    for path, folder, url_prefix in sorted(post_sources, key=lambda s: str(s[0])):
        doc = load_doc(path, md, url_prefix, folder=folder)
        if doc.draft and not include_drafts:
            print(f"  · skipping draft: {path.name}")
            continue
        if doc.draft:
            doc.title += "  [draft]"
        posts.append(doc)
    posts.sort(key=lambda d: d.date or date.min, reverse=True)

    pages = [load_doc(p, md, "") for p in sorted((CONTENT / "pages").glob("*.md"))]
    return posts, pages


# ─────────────────────────────────────────────────────────────
# Templating (a deliberately tiny {{placeholder}} substitution)
# ─────────────────────────────────────────────────────────────

def render(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return re.sub(r"\{\{\w+\}\}", "", template)


SOCIAL_ICONS = {
    "github": '<path d="M12 2A10 10 0 0 0 8.84 21.5c.5.08.66-.23.66-.5v-1.7C6.73 19.91 6.14 18 6.14 18a2.7 2.7 0 0 0-1.13-1.49c-.92-.63.07-.62.07-.62a2.14 2.14 0 0 1 1.56 1.05 2.17 2.17 0 0 0 2.96.85 2.18 2.18 0 0 1 .65-1.37c-2.27-.26-4.65-1.14-4.65-5.06a3.96 3.96 0 0 1 1.05-2.75 3.68 3.68 0 0 1 .1-2.71s.86-.28 2.8 1.05a9.62 9.62 0 0 1 5.1 0c1.94-1.33 2.8-1.05 2.8-1.05a3.68 3.68 0 0 1 .1 2.71 3.96 3.96 0 0 1 1.05 2.75c0 3.93-2.39 4.8-4.67 5.05a2.43 2.43 0 0 1 .69 1.88v2.79c0 .27.16.59.67.5A10 10 0 0 0 12 2Z"/>',
    "twitter": '<path d="M18.9 2.5h3.4l-7.4 8.5 8.7 11.5h-6.8l-5.3-7-6.1 7H2l7.9-9-8.3-11h7l4.8 6.4Zm-1.2 18h1.9L7.4 4.4H5.4Z"/>',
    "linkedin": '<path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3zM10 9h3.8v1.7h.05a4.2 4.2 0 0 1 3.75-2.05c4 0 4.75 2.6 4.75 6V21h-4v-5.6c0-1.35-.02-3.1-1.9-3.1s-2.2 1.47-2.2 3v5.7h-4Z"/>',
    "instagram": '<path d="M12 2.2c3.2 0 3.6 0 4.85.07 3.25.15 4.77 1.69 4.92 4.92.06 1.25.07 1.65.07 4.85s-.01 3.6-.07 4.85c-.15 3.23-1.66 4.77-4.92 4.92-1.25.06-1.64.07-4.85.07s-3.6-.01-4.85-.07c-3.26-.15-4.77-1.7-4.92-4.92C2.17 15.6 2.16 15.2 2.16 12s.01-3.6.07-4.85C2.38 3.92 3.9 2.38 7.15 2.23 8.4 2.18 8.8 2.2 12 2.2Zm0 3.1a6.7 6.7 0 1 0 0 13.4 6.7 6.7 0 0 0 0-13.4Zm0 11.05a4.35 4.35 0 1 1 0-8.7 4.35 4.35 0 0 1 0 8.7Zm6.96-11.32a1.56 1.56 0 1 0 0 3.13 1.56 1.56 0 0 0 0-3.13Z"/>',
    "youtube": '<path d="M23 12s0-3.9-.5-5.75a3 3 0 0 0-2.1-2.12C18.55 3.6 12 3.6 12 3.6s-6.55 0-8.4.53A3 3 0 0 0 1.5 6.25C1 8.1 1 12 1 12s0 3.9.5 5.75a3 3 0 0 0 2.1 2.12c1.85.53 8.4.53 8.4.53s6.55 0 8.4-.53a3 3 0 0 0 2.1-2.12C23 15.9 23 12 23 12ZM9.75 15.5v-7l6.25 3.5Z"/>',
    "mastodon": '<path d="M21.6 8.9c0-4.2-2.7-5.4-2.7-5.4C17.5 2.8 15.2 2.5 12.8 2.5h-.06c-2.4 0-4.7.3-6.1.99 0 0-2.7 1.2-2.7 5.4v3.2c0 4.5.7 8.9 4.9 10 1.9.5 3.6.6 5 .55 2.5-.14 3.9-.9 3.9-.9l-.08-1.8s-1.8.56-3.8.5c-2-.07-4.1-.22-4.4-2.68a4.9 4.9 0 0 1-.05-.68s2 .5 4.5.6c1.5.08 2.9-.09 4.4-.27 2.8-.33 5.2-2.05 5.5-3.62.5-2.47.46-6.03.46-6.03Zm-3.4 5.6h-2.1V9.4c0-1.1-.46-1.65-1.4-1.65-1 0-1.55.67-1.55 2v2.9h-2.1v-2.9c0-1.33-.54-2-1.55-2-.93 0-1.4.56-1.4 1.65v5.1H6V9.24c0-1.09.28-1.96.84-2.6a2.9 2.9 0 0 1 2.25-.96c1.06 0 1.87.4 2.4 1.22l.52.88.53-.88c.53-.81 1.34-1.22 2.4-1.22.94 0 1.7.32 2.25.97.56.63.84 1.5.84 2.59Z"/>',
    "email": '<path d="M2 5.5A2.5 2.5 0 0 1 4.5 3h15A2.5 2.5 0 0 1 22 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 18.5Zm2.4-.5 7.6 6 7.6-6Zm15.6 1.9-7.35 5.8a1 1 0 0 1-1.3 0L4 6.9V19h16Z"/>',
    "rss": '<path d="M5 3a16 16 0 0 1 16 16h-3A13 13 0 0 0 5 6Zm0 7a9 9 0 0 1 9 9h-3a6 6 0 0 0-6-6Zm1.5 6a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z"/>',
    "link": '<path d="M10.6 13.4a1 1 0 0 1 0-1.4l2.8-2.8a3 3 0 1 1 4.2 4.2l-1.4 1.4-1.4-1.4 1.4-1.4a1 1 0 1 0-1.4-1.4L12 13.4a1 1 0 0 1-1.4 0Zm2.8-2.8a1 1 0 0 1 0 1.4l-2.8 2.8a1 1 0 1 0 1.4 1.4l1.4-1.4 1.4 1.4-1.4 1.4a3 3 0 1 1-4.2-4.2l2.8-2.8a1 1 0 0 1 1.4 0Z"/>',
}


def normalize_url(url: str) -> str:
    """Add a scheme to bare domains.

    A browser reads `www.example.com` as a path relative to the current page,
    so it would resolve against your own site instead of going anywhere.
    """
    url = url.strip()
    if not url or url.startswith(("/", "#")):
        return url
    if re.match(r"^[a-zA-Z][\w+.-]*:", url):  # already has http:, mailto:, etc.
        return url
    return "https://" + url


def social_links(socials: list[dict]) -> str:
    items = []
    for social in socials:
        icon_name = social.get("icon", "link").strip().lower()
        if icon_name not in SOCIAL_ICONS:
            print(
                f"  ! unknown social icon {icon_name!r} — using the generic one.\n"
                f"    Available: {', '.join(sorted(SOCIAL_ICONS))}"
            )
        icon = SOCIAL_ICONS.get(icon_name, SOCIAL_ICONS["link"])

        name = html.escape(social.get("name", "Link"))
        target = normalize_url(social.get("url", "#"))
        if target != social.get("url", "#").strip():
            print(f"  · {social.get('name', 'link')}: added https:// to {social['url']!r}")

        url = html.escape(target)
        external = (
            ' target="_blank" rel="noopener noreferrer"'
            if target.startswith(("http://", "https://"))
            else ""
        )
        items.append(
            f'<a class="social" href="{url}" title="{name}" aria-label="{name}"{external}>'
            f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{icon}</svg>'
            f"</a>"
        )
    return "\n        ".join(items)


def nav_html(posts: list[Doc], pages: list[Doc], current: Doc | None, prefix: str) -> str:
    """Site nav: Home, standalone pages, then posts — loose ones under "Posts"
    and each folder as its own group."""
    lines = []

    home_class = ' class="nav-link current"' if current is None else ' class="nav-link"'
    lines.append(f'<a href="{prefix}index.html"{home_class}>Home</a>')
    for page in pages:
        if page.nav_hidden:
            continue
        active = " current" if current is page else ""
        lines.append(
            f'<a href="{prefix}{page.url}" class="nav-link{active}">{html.escape(page.title)}</a>'
        )

    lines.append('<div class="nav-heading">Writing</div>')
    lines.append(
        '<input type="search" id="nav-filter" class="nav-filter" '
        'placeholder="Filter posts…" aria-label="Filter posts">'
    )

    if not posts:
        lines.append('<p class="nav-empty">No posts yet.</p>')
        return "\n          ".join(lines)

    def group(label: str, group_posts: list[Doc]) -> str:
        block = ['<div class="nav-group">']
        if label:
            block.append(f'<div class="nav-subheading">{html.escape(label)}</div>')
        block.append('<ul class="nav-posts">')
        for post in group_posts:
            active = " current" if current is post else ""
            block.append(
                f'<li><a href="{prefix}{post.url}" class="nav-link{active}">'
                f'<span class="nav-title">{html.escape(post.title)}</span>'
                f'<span class="nav-date">{post.date_display}</span></a></li>'
            )
        block.append("</ul></div>")
        return "\n          ".join(block)

    loose = [p for p in posts if not p.folder]
    folders = sorted({p.folder for p in posts if p.folder})

    if folders:
        # Loose posts go under a "Posts" heading; each folder is its own group.
        if loose:
            lines.append(group("Posts", loose))
        for folder in folders:
            folder_posts = [p for p in posts if p.folder == folder]
            lines.append(group(folder_posts[0].folder_label, folder_posts))
    else:
        # No folders in use — a single flat list, as before (no "Posts" label).
        lines.append(group("", loose))

    lines.append('<p class="nav-empty" id="nav-no-results" hidden>No posts match.</p>')
    return "\n          ".join(lines)


def post_list_html(posts: list[Doc], prefix: str) -> str:
    if not posts:
        return (
            '<p class="empty">No posts yet — drop a markdown file into '
            "<code>content/posts/</code> and run <code>./build</code>.</p>"
        )
    cards = []
    for post in posts:
        cards.append(f"""<article class="post-card">
            <h2 class="post-card-title"><a href="{prefix}{post.url}">{html.escape(post.title)}</a></h2>
            <p class="post-meta"><time datetime="{post.date_iso}">{post.date_display}</time></p>
            <p class="post-summary">{html.escape(post.summary)}</p>
          </article>""")
    return "\n          ".join(cards)


# A table of contents needs at least this many entries to be worth showing.
TOC_MIN_ENTRIES = 2


def _flatten_toc(tokens: list, out: list) -> None:
    """Collect (level, "#anchor", name) for every H2/H3 in a rendered article."""
    for token in tokens:
        if token.get("level") in (2, 3) and token.get("id"):
            out.append((token["level"], "#" + token["id"], token.get("name", "")))
        _flatten_toc(token.get("children") or [], out)


def _toc_markup(entries: list, heading: str) -> str:
    """Render a TOC panel from a list of (level, href, label), or "" if too short.

    Emits a floating button (shown only on narrow screens) plus a panel of
    links. The panel is a sticky rail on wide screens and a popup on mobile —
    which is which is decided entirely in CSS, so this markup is the same for
    both. Purely additive: pages with too few entries get no TOC at all.
    """
    if len(entries) < TOC_MIN_ENTRIES:
        return ""

    items = []
    for level, href, label in entries:
        cls = "toc-l2" if level == 2 else "toc-l3"
        items.append(f'<a class="{cls}" href="{html.escape(href)}">{html.escape(label)}</a>')
    link_html = "\n        ".join(items)

    heading = html.escape(heading)
    list_icon = ('<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" '
                 'stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/>')
    return f"""<aside class="toc" aria-label="{heading}">
    <button class="toc-fab" type="button" aria-expanded="false" aria-controls="toc-panel" aria-label="{heading}">
      <svg viewBox="0 0 24 24" aria-hidden="true">{list_icon}</svg>
    </button>
    <div class="toc-panel" id="toc-panel">
      <p class="toc-heading">{heading}</p>
      <nav class="toc-links">
        {link_html}
      </nav>
    </div>
  </aside>"""


def toc_html(toc_tokens: list) -> str:
    """The in-page table of contents for an article (post or standalone page)."""
    links: list[tuple[int, str, str]] = []
    _flatten_toc(toc_tokens, links)
    return _toc_markup(links, "On this page")


def home_toc_html(posts: list[Doc], prefix: str = "") -> str:
    """The home page isn't an article, so its "contents" is the list of posts."""
    entries = [(2, f"{prefix}{post.url}", post.title) for post in posts]
    return _toc_markup(entries, "Posts")


# ─────────────────────────────────────────────────────────────
# CSS generation
# ─────────────────────────────────────────────────────────────

TOP_LEVEL_KEYS = {"title", "tagline", "author", "intro", "palette"}


def check_config(config: dict) -> None:
    """Catch settings that fell into [[socials]] through TOML section ordering.

    In TOML everything after a [section] header belongs to that section, so a
    stray `palette = "…"` below [[socials]] is silently swallowed rather than
    read as a site setting.
    """
    stray = set()
    for social in config.get("socials", []):
        stray |= TOP_LEVEL_KEYS & set(social)

    if stray:
        names = ", ".join(sorted(stray))
        raise SystemExit(
            f"site.toml: {names} ended up inside the [[socials]] section.\n"
            "Move it above the first [[socials]] block — in TOML, everything "
            "after a [section] header belongs to that section."
        )


# Minimum WCAG AA contrast ratio each role needs against the background it sits
# on. 4.5 is the threshold for normal body text; 3.0 covers large/bold text,
# which the headings are. mark_text is measured against mark_bg, not the page.
CONTRAST_TARGETS = {
    "text": 4.5, "muted": 4.5, "bold": 4.5, "italic": 4.5, "link": 4.5,
    "title": 3.0, "h1": 3.0, "h2": 3.0, "h3": 3.0,
}


def _relative_luminance(hex_color: str) -> float:
    c = hex_color.lstrip("#")
    if len(c) != 6:
        raise ValueError(f"expected a #rrggbb colour, got {hex_color!r}")
    channels = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_contrast(palettes: dict) -> bool:
    """Report the WCAG contrast of every palette in both modes.

    Returns True if every colour clears its target, so a caller can decide
    whether to treat failures as an error.
    """
    all_pass = True
    for name, palette in palettes.items():
        print(f"\n{name}")

        missing = []
        for role in COLOR_ROLES:
            value = palette.get(role)
            if not isinstance(value, dict) or not {"light", "dark"} <= set(value):
                missing.append(role)
        if missing:
            all_pass = False
            print(f"    FAIL incomplete — missing light/dark for: {', '.join(missing)}")
            continue

        for mode in ("light", "dark"):
            bg = palette["bg"][mode]
            print(f"  {mode}  (background {bg})")
            for role, minimum in CONTRAST_TARGETS.items():
                ratio = contrast_ratio(palette[role][mode], bg)
                ok = ratio >= minimum
                all_pass &= ok
                flag = "  ok " if ok else "  FAIL"
                print(f"    {flag} {role:6s} {palette[role][mode]}  {ratio:5.2f}:1"
                      + ("" if ok else f"  (needs {minimum})"))
            # Highlighted text sits on mark_bg, so check that pairing instead.
            ratio = contrast_ratio(palette["mark_text"][mode], palette["mark_bg"][mode])
            ok = ratio >= 4.5
            all_pass &= ok
            flag = "  ok " if ok else "  FAIL"
            print(f"    {flag} {'mark':6s} {palette['mark_text'][mode]} on "
                  f"{palette['mark_bg'][mode]}  {ratio:5.2f}:1"
                  + ("" if ok else "  (needs 4.5)"))

    print("\n" + "─" * 52)
    print("All colours meet WCAG AA." if all_pass
          else "Some colours are below target — see FAIL rows above.")
    return all_pass


def resolve_palettes(config: dict, available: dict) -> dict:
    """Which palette to use for each mode.

    `palette` in site.toml is either one name for both modes:

        palette = "rose-pine"

    or a different palette per mode:

        palette = { light = "rose-pine", dark = "tokyo-night" }
    """
    chosen = config.get("palette", "rose-pine")
    if isinstance(chosen, str):
        chosen = {"light": chosen, "dark": chosen}

    unknown = [(m, n) for m, n in chosen.items() if n not in available]
    if unknown:
        lines = "\n".join(f"  {mode}: {name!r}" for mode, name in unknown)
        raise SystemExit(
            f"site.toml asks for a palette that isn't in palettes.toml:\n{lines}\n"
            f"Available: {', '.join(sorted(available))}"
        )

    missing = {"light", "dark"} - set(chosen)
    if missing:
        raise SystemExit(
            f"site.toml: palette is missing a value for {', '.join(sorted(missing))}.\n"
            'Use palette = "name", or palette = { light = "…", dark = "…" }.'
        )

    return chosen


def load_colors(config: dict) -> tuple[str, dict, dict]:
    """The chosen palettes, with any per-colour overrides from site.toml applied.

    Each mode is filled in from its own palette, so mixing two is safe — light
    and dark never render at the same time, and each stays internally coherent.
    """
    palettes = tomllib.loads(PALETTES_FILE.read_text(encoding="utf-8"))
    chosen = resolve_palettes(config, palettes)

    colors: dict[str, dict[str, str]] = {}
    for mode, name in chosen.items():
        for role, value in palettes[name].items():
            if isinstance(value, dict) and mode in value:
                colors.setdefault(role, {})[mode] = value[mode]

    # Overrides are merged per mode, so you can restyle just one of them.
    overrides = config.get("colors", {})
    stray = sorted(set(overrides) - set(COLOR_ROLES))
    if stray:
        raise SystemExit(
            f"site.toml [colors]: unknown name(s) {', '.join(stray)}.\n"
            f"Valid names: {', '.join(COLOR_ROLES)}"
        )
    for role, value in overrides.items():
        colors.setdefault(role, {}).update(value)

    code = {
        "light": palettes[chosen["light"]].get("code_light", "default"),
        "dark": palettes[chosen["dark"]].get("code_dark", "monokai"),
    }

    problems = []
    for role in COLOR_ROLES:
        value = colors.get(role)
        if value is None:
            problems.append(f"{role} is missing")
        elif not ("light" in value and "dark" in value):
            have = ", ".join(sorted(value)) or "nothing"
            problems.append(f"{role} needs both a light and a dark value (has {have})")
    if problems:
        raise SystemExit("Colour problems in site.toml:\n  " + "\n  ".join(problems))

    if chosen["light"] == chosen["dark"]:
        label = chosen["light"]
    else:
        label = f"{chosen['light']} (light) + {chosen['dark']} (dark)"

    return label, colors, code


def theme_css(colors: dict) -> str:
    def block(mode: str) -> str:
        return "\n".join(
            f"  --{name.replace('_', '-')}: {value[mode]};" for name, value in colors.items()
        )

    light, dark = block("light"), block("dark")
    return f"""/* Generated by build.py from site.toml — edit the colours there. */
:root {{
{light}
  color-scheme: light;
}}

:root[data-theme="dark"] {{
{dark}
  color-scheme: dark;
}}

@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
{dark}
    color-scheme: dark;
  }}
}}
"""


def code_css(styles: dict) -> str:
    light = HtmlFormatter(style=styles["light"]).get_style_defs(".codehilite")
    dark = HtmlFormatter(style=styles["dark"]).get_style_defs(".codehilite")
    dark_scoped = "\n".join(
        f':root[data-theme="dark"] {line}' if line.startswith(".codehilite") else line
        for line in dark.splitlines()
    )
    media_dark = "\n".join(
        f'  :root:not([data-theme="light"]) {line}' if line.startswith(".codehilite") else f"  {line}"
        for line in dark.splitlines()
    )
    return (
        "/* Generated by build.py — syntax highlighting for fenced code blocks. */\n"
        f"{light}\n\n{dark_scoped}\n\n"
        f"@media (prefers-color-scheme: dark) {{\n{media_dark}\n}}\n"
    )


# ─────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def asset_version() -> str:
    """A short hash of the CSS and JS, appended to their URLs as ?v=…

    Without it, browsers keep serving a cached stylesheet after a rebuild — so
    a restyle looks like it did nothing until you force-refresh.
    """
    digest = hashlib.md5()
    for path in sorted((DIST / "assets").rglob("*")):
        if path.suffix in (".css", ".js"):
            digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


def build(include_drafts: bool = False) -> None:
    config = tomllib.loads((ROOT / "site.toml").read_text(encoding="utf-8"))
    check_config(config)
    site_title = config.get("title", "Blog")
    socials = social_links(config.get("socials", []))
    palette_name, colors, code_styles = load_colors(config)

    print(f"Building… (palette: {palette_name})")
    posts, pages = load_all(include_drafts)

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ASSETS, DIST / "assets", ignore=shutil.ignore_patterns(".DS_Store"))
    write(DIST / "assets/css/theme.css", theme_css(colors))
    write(DIST / "assets/css/code.css", code_css(code_styles))
    write(DIST / ".nojekyll", "")

    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    doc_tpl = (TEMPLATES / "document.html").read_text(encoding="utf-8")
    home_tpl = (TEMPLATES / "home.html").read_text(encoding="utf-8")

    version = asset_version()

    def page_shell(*, doc: Doc | None, prefix: str, title: str, description: str,
                   body: str, toc: str = "") -> str:
        return render(
            base,
            root=prefix,
            v=version,
            toc=toc,
            page_title=html.escape(title),
            site_title=html.escape(site_title),
            description=html.escape(description),
            nav=nav_html(posts, pages, doc, prefix),
            socials=socials,
            tagline=html.escape(config.get("tagline", "")),
            year=str(date.today().year),
            author=html.escape(config.get("author", "")),
            content=body,
        )

    # Home page — from content/home.md if you've written one, else the built-in
    # template. In home.md, a line that is just `{posts}` is replaced by the
    # automatic post list; leave it out to hand-author the whole page.
    home_src = CONTENT / "home.md"
    if home_src.exists():
        home_md = make_markdown()
        rendered_home = process_body(home_md.convert(home_src.read_text(encoding="utf-8")), "")
        # The first heading becomes the page title (gets the title colour, not h1).
        rendered_home = re.sub(r"<h1(\s|>)", r'<h1 class="doc-title"\1', rendered_home, count=1)
        post_list = post_list_html(posts, "")
        rendered_home = re.sub(
            r"<p>\s*\{posts\}\s*</p>", lambda _m: post_list, rendered_home, count=1
        )
        home_body = f'<article class="prose">\n{rendered_home}\n</article>'
    else:
        home_body = render(
            home_tpl,
            site_title=html.escape(site_title),
            intro=html.escape(config.get("intro", "")),
            posts=post_list_html(posts, ""),
            count=str(len(posts)),
        )
    write(DIST / "index.html", page_shell(
        doc=None, prefix="", title=site_title,
        description=config.get("tagline", ""), body=home_body,
        toc=home_toc_html(posts, ""),
    ))
    print(f"  ✓ index.html ({len(posts)} posts)")

    # Posts and pages
    for doc in posts + pages:
        is_post = doc in posts
        meta_line = (
            f'<p class="post-meta"><time datetime="{doc.date_iso}">{doc.date_display}</time>'
            f"</p>"
            if is_post else ""
        )
        body = render(
            doc_tpl,
            title=html.escape(doc.title),
            meta=meta_line,
            body=doc.body,
        )
        write(DIST / doc.url / "index.html", page_shell(
            doc=doc, prefix=doc.root_prefix,
            title=f"{doc.title} · {site_title}",
            description=doc.summary, body=body,
            toc=toc_html(doc.toc_tokens),
        ))
        print(f"  ✓ {doc.url}")

    print(f"\nDone. {len(posts)} post(s), {len(pages)} page(s) → dist/")


def package_zip() -> Path:
    """Zip the built site for upload to hosts that take a drag-and-dropped folder.

    The archive holds the *contents* of dist/ at its top level — so index.html
    sits at the root of the zip — and skips junk like .DS_Store.
    """
    import zipfile

    archive = ROOT / "site.zip"
    archive.unlink(missing_ok=True)

    skip = {".DS_Store"}
    count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(DIST.rglob("*")):
            if path.is_dir() or path.name in skip:
                continue
            zf.write(path, path.relative_to(DIST))
            count += 1

    size_kb = archive.stat().st_size / 1024
    print(f"Packaged {count} files → {archive.name} ({size_kb:.0f} KB)")
    print("  Its top level holds index.html — upload the zip, or unzip and "
          "upload the files inside.")
    return archive


def main() -> int:
    args = sys.argv[1:]

    if "--check" in args:
        palettes = tomllib.loads(PALETTES_FILE.read_text(encoding="utf-8"))
        ok = check_contrast(palettes)
        return 0 if ok else 1

    build(include_drafts="--drafts" in args)

    if "--zip" in args:
        package_zip()

    if "--serve" in args:
        import http.server
        import socketserver

        handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(
            *a, directory=str(DIST), **kw
        )
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("\nServing at http://localhost:8000  (Ctrl-C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
