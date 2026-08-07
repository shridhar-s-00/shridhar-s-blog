---
Title: Hello, world
Date: 2026-07-20
Summary: The first post — what this space is for and how it gets published.
---

This is the first post. It exists mostly so the site has something to show, and
so you have a short file to copy when you write the next one.

## Writing a post

Every post is one markdown file in `content/posts/`. The filename becomes the URL,
so `content/posts/hello-world.md` is published at `/posts/hello-world/`.

At the top of each file there's a small block of information between two lines of
dashes:

```text
---
Title: Hello, world
Date: 2026-07-20
Summary: A sentence that shows up in the post list.
---
```

Only `Title` and `Date` really matter. If you leave the summary out, the first
paragraph gets used instead.

## Publishing

Run `./build` and the whole site is regenerated into `dist/`. Commit and push, and
GitHub Pages picks it up a minute later. That's the entire workflow — ==there is no
database and no admin panel to log into==.

If you want to work on something without publishing it yet, add `Draft: true` to
the block at the top. It will be skipped unless you build with `./build --drafts`.
