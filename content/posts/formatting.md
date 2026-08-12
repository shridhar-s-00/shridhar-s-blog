---
Title: Everything you can write in a post
Date: 2026-07-22
Draft: true
Summary: A reference for every formatting feature this blog supports — headings, emphasis, highlights, images, downloads, tables and code.
---

# Everything you must know
This post is a working reference. Keep it around; delete it when you no longer need it.
Everything below is plain markdown, and every feature shown here renders on your site.

## Headings get their own colours

There are three coloured levels. Use them in order and the page stays readable.
The title above the post is level one, `##` is level two, and `###` is level three.

### This is a level-three heading

Levels four and below stay in the normal text colour on purpose, so the three
coloured levels keep their meaning.

## Emphasis

Write **bold text with two asterisks** and *italics with one*. Both get their own
colour from the active palette. You can ==highlight a phrase with double equals
signs== when you want it to jump off the page.

Combine them freely: ***bold italic***, `inline code`, and ~~strikethrough~~.

> Block quotes are for pulling out someone else's words.
> They run to as many lines as you need.

## Links and social profiles

An [ordinary link](https://example.com) opens in a new tab automatically when it
points off-site. Links to your own pages stay in the same tab.

Your social profiles live in `site.toml` and appear at the bottom of the sidebar —
you don't need to write them into posts.

## Images

Drop image files into `assets/images/` and reference them like this:

![A gradient placeholder](assets/images/sample.png "Add a caption by putting text in quotes after the path")

The path always starts with `assets/` no matter how deep the post sits. Any image
on its own line becomes a centred figure, and the quoted text becomes the caption.
Leave the quotes out and you get an image with no caption.

## Downloads

Link to a file the same way you link to a page, and it turns into a download button:

[Download the sample PDF](assets/files/sample.pdf)

Put your files in `assets/files/`. This works for `.pdf`, `.zip`, `.docx`, `.xlsx`,
`.pptx`, `.csv` and `.epub`.

## Lists

1. Numbered lists work
2. So do nested ones — indent the nested items by **4 spaces**:
    - like this
    - and this
3. Back to the top level

Separate a list from the paragraph above it with a blank line, or the lines
fold together into one paragraph.

## Tables

| Feature   | Syntax     | Colour comes from        |
|-----------|------------|--------------------------|
| Bold      | `**text**` | palette → `bold`         |
| Italic    | `*text*`   | palette → `italic`       |
| Highlight | `==text==` | palette → `mark_bg`      |

Switch the whole site between Rosé Pine, Catppuccin and Tokyo Night by changing
one line in `site.toml` — either one palette for both modes, or a different one
for each:

```toml
palette = "rose-pine"

palette = { light = "rose-pine", dark = "tokyo-night" }
```

## Code

Fenced code blocks are syntax-highlighted, and they match whichever theme is active:

```python
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


print(greet("world"))
```

## Footnotes

You can add a footnote like this[^1] and it lands at the bottom of the page.

[^1]: Here is the footnote. Write it anywhere in the file; it always renders last.
