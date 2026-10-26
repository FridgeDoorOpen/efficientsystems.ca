# efficientsystems.ca

Static site for Efficient Systems Canada, self-hosted on the NAS (Nginx behind a Cloudflare Tunnel).

## Layout

- `/` — ESC home, `/principles/`, `/legend/` — built by `build.py` from `content/` and `templates/`
- `/teaching/` — index of classroom tools (not linked from the ESC root)
- `/teaching/<tool>/index.html` — one folder per tool

## Adding a classroom tool

1. Create `public/teaching/<tool-name>/index.html`
2. Add `<meta name="robots" content="noindex, nofollow">` in its `<head>`
3. Add a link to it in `public/teaching/index.html`
4. Push, then pull on the NAS

## Building

`uv run build.py` writes only the paths listed in `OWNED` inside `public/`. Teaching tools and `robots.txt` are never touched.

## Search engines

`robots.txt` asks crawlers to skip `/teaching/`, and each teaching page carries a `noindex` tag.
Neither is access control: anyone with the URL can open these pages.

## Serving

Only `public/` is served by Nginx. Anything outside it (this README, `.git/`) is never reachable from the web.
