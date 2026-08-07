# Blog

A personal blog that turns markdown files into a static website. No database,
no admin panel, no JavaScript framework — you write a `.md` file, run one
command, and push.

## Writing a post

Create a file in `content/posts/`. The filename becomes the URL, so
`content/posts/hello-world.md` is published at `/posts/hello-world/`.

```markdown
---
Title: Hello, world
Date: 2026-07-20
Summary: One sentence for the post list. Optional.
---

Your writing starts here.
```

Or let the helper script do it:

```sh
./new "The title of my post"
```

That creates the file with today's date, marked as a draft.

### Front matter

| Field     | Required | What it does                                              |
|-----------|----------|-----------------------------------------------------------|
| `Title`   | yes      | Shown as the heading and in the sidebar                    |
| `Date`    | yes      | `YYYY-MM-DD`. Sorts the post list, newest first            |
| `Summary` | no       | Blurb in the post list; falls back to the first paragraph  |
| `Draft`   | no       | `true` keeps it unpublished until you remove the line      |
| `Slug`    | no       | Override the URL if you don't want the filename used       |

## Building and previewing

```sh
./build            # regenerate dist/
./build --serve    # regenerate, then serve at http://localhost:8000
./build --drafts   # include posts marked Draft: true
./build --zip      # regenerate, then package dist/ into site.zip
```

The first run creates a virtualenv and installs the two dependencies
(`markdown` and `Pygments`) automatically.

Everything in `dist/` is generated — never edit it by hand, and don't commit it.

## Formatting

Standard markdown, plus a few extras:

- `==highlighted text==` renders with a coloured background
- `~~strikethrough~~`
- `- [x]` / `- [ ]` become checkboxes
- Tables, footnotes, and fenced code blocks with syntax highlighting

The post **Everything you can write in a post** is a live reference for all of
it. Delete it once you don't need it.

### Images

Put files in `assets/images/` and reference them starting with `assets/`,
regardless of how deep the post lives:

```markdown
![Alt text](assets/images/photo.jpg "An optional caption")
```

An image on its own line becomes a centred figure; quoted text after the path
becomes the caption.

### Downloads

Put files in `assets/files/` and link to them normally:

```markdown
[Download my CV](assets/files/cv.pdf)
```

Links to `.pdf`, `.zip`, `.docx`, `.xlsx`, `.pptx`, `.csv` and `.epub` are
automatically styled as a download button.

## Pages

Files in `content/pages/` become standalone pages — an About page, a projects
page, whatever — listed above the writing in the sidebar. They don't take a
date. Add `Nav: false` to keep one out of the sidebar.

## Configuration

Everything lives in `site.toml`:

- **Site title, tagline, author, and the intro on the home page**
- **Social links** — add or remove `[[socials]]` blocks. Available icons:
  `github`, `twitter`, `linkedin`, `instagram`, `youtube`, `mastodon`,
  `email`, `rss`, `link`
- **Colours** — pick a palette with one line

### Palettes

One palette for both modes:

```toml
palette = "rose-pine"    # or "catppuccin" or "tokyo-night"
```

Or a different one for each mode:

```toml
palette = { light = "rose-pine", dark = "tokyo-night" }
```

| Palette       | Light / dark variants | Character               |
|---------------|-----------------------|-------------------------|
| `rose-pine`   | Dawn / Main           | Muted, warm, low-glare  |
| `catppuccin`  | Latte / Mocha         | Pastel, higher contrast |
| `tokyo-night` | Day / Night           | Cooler, more saturated  |

Each palette uses its theme's own light *and* dark variants, so the two modes
are separately designed rather than one set of hues brightened and dimmed. Each
also brings a matching syntax-highlighting theme for code blocks.

Mixing two palettes is safe: light and dark never render at the same time, and
each mode — background, text, all three heading levels, code — is filled in
entirely from its own palette, so neither ends up half one theme and half
another.

The definitions live in `palettes.toml`. To change individual colours without
leaving the palette, uncomment the `[colors]` block in `site.toml`. Overrides
are merged per mode, so you can restyle just one:

```toml
[colors]
h1 = { dark = "#ff8888" }    # light stays as the palette has it
```

A handful of accents are darkened from the originals for light mode: these
themes were designed for code editors, and some of their pastels don't hold up
as body text on a light background. Every colour meets WCAG AA contrast.

Change a palette or a colour, run `./build`, and the whole site restyles.

> One TOML gotcha: plain settings like `palette` and `title` must stay **above**
> the `[[socials]]` section. Anything after a `[section]` header belongs to that
> section. The build will tell you if you get this wrong.

### Making your own theme

1. Open `palettes.toml` and copy the commented `[my-theme]` template at the
   bottom. Rename it and fill in every colour — each needs a `light` and a
   `dark` value.
2. Check it's readable:

   ```sh
   ./build --check
   ```

   This prints the WCAG contrast ratio of every colour in every palette and
   flags anything too faint to read (body text needs 4.5:1, headings 3.0:1).
   It exits non-zero if anything fails, so it also works as a CI gate.
3. Use it in `site.toml`: `palette = "my-theme"`.

The 13 colour roles are: `bg`, `surface`, `text`, `muted`, `border`, `h1`,
`h2`, `h3`, `bold`, `italic`, `mark_bg`, `mark_text`, `link`. Each theme also
sets `code_light` / `code_dark` — any [Pygments style][pyg] name — for fenced
code blocks. List the available styles with:

```sh
.venv/bin/python -c "from pygments.styles import get_all_styles as g; print(*sorted(g()))"
```

[pyg]: https://pygments.org/styles/

## Publishing to GitHub Pages

One-time setup:

1. `git init && git add . && git commit -m "Initial commit"`
2. Create an empty repository on GitHub and push to it (branch `main`)
3. In the repository, go to **Settings → Pages** and set **Source** to
   **GitHub Actions**

After that, every push to `main` rebuilds and republishes the site
automatically via `.github/workflows/deploy.yml`. You don't need to build or
commit `dist/` yourself.

## Hosting anywhere else

The site is plain static files with relative links, so it runs from any web
host, a subfolder, or even straight off disk — no server-side anything.

```sh
./build --zip
```

This produces `site.zip` with `index.html` at its top level. Then:

- **Netlify / Cloudflare Pages / Neocities** — drag `site.zip` (or the `dist/`
  folder) onto their upload area.
- **Shared / cPanel hosting** — unzip and upload the *contents* into
  `public_html/` (so `index.html` lands there, not inside a subfolder).
- **Amazon S3, a USB stick, a LAN share** — copy the files in; open
  `index.html`.

The key rule for every host: upload what's **inside** `dist/` (or inside the
zip), not the `dist` folder itself — `index.html` must sit at the location you
want the site's home page to be.

## How it fits together

```
content/posts/*.md     your writing
content/pages/*.md     standalone pages
assets/                images, downloadable files, CSS, JS
templates/             the HTML shell (base, post, home)
site.toml              title, socials, palette choice
palettes.toml          the three colour palettes
build.py               turns all of the above into dist/
dist/                  the generated site (git-ignored)
site.zip               dist/ packaged for upload (git-ignored, from --zip)
```
