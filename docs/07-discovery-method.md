# 07 — Discovery method: how you find URL / delay / header / selector answers

The reusable playbook used to build this scraper. Apply it to ANY site.

## Step 0 — Is scraping OK here?

Check `robots.txt` (`https://site/robots.txt`), the site's terms, and scrape
politely (rate limits, off-peak, only what you need). For Ralph Lauren, robots.txt
disallows `*/search*`, facet params (`*prefn1*`, `*srule*`, `*pmin*`) and
account/checkout paths → our crawl uses clean category URLs only, and
`ROBOTSTXT_OBEY = True` enforces the rest mechanically.

## Step 1 — Pick entry URLs

1. Browse the site like a human; copy category URLs from the address bar
   (cleanest URLs, no tracking params).
2. Read `robots.txt`'s `Sitemap:` line for category discovery at scale.
3. Prefer listing pages over search pages (search is commonly disallowed).

## Step 2 — Determine the anti-bot reality

Quick test from your machine: `curl -I https://site` (or any fetch tool).
- Normal 200 HTML → plain Scrapy may work.
- 403/307/challenge page → you need Zyte API (residential + browser rendering).

Ralph Lauren 307-redirected plain requests here → that single observation is
why this project uses Zyte API. Keep evidence like this when justifying
architecture.

## Step 3 — Find extraction data (selectors)

For each page type, in order of preference:

1. **JSON-LD / structured data** — in DevTools console:
   ```js
   JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)
   ```
   If a `Product` object with name/offers/image exists → parse JSON-LD (stable,
   standardized). This is why `ProductPage` is JSON-LD-first.
2. **CSS selectors** — F12 → Elements → right-click the product name →
   *Inspect* → right-click node → Copy → *selector*. Prefer semantic attributes
   (`data-testid`, `itemprop`) over generated class names — they change less.
3. Test candidates in the console before writing code:
   `document.querySelectorAll('a.thumb-link').length`
4. Drop verified selectors into the page object's `selectors` dict and add a
   fixture to `tests/test_page_objects.py`.

## Step 4 — Find the location/zip mechanism (if scraping varies by zip)

1. DevTools → Network tab → clear it → use the site's "delivery location"
   modal to enter a zip.
2. Watch what fires: a POST to an API? a `Set-Cookie`? a URL param?
3. Cases:
   - URL param → simplest: add it in the mixin.
   - Cookie only → you could replay it, **but** the server may also check IP
     geolocation (cookie says 90210, IP says Germany → mismatch = blocked).
   - IP-checked (or unsure) → use **Zyte sessions + `setLocation`**, which pins
     IP *and* cookies consistently. This project chose that path.

## Step 5 — Choose delays

1. robots.txt `Crawl-delay:` if present (Ralph Lauren: none).
2. Else start conservative: `DOWNLOAD_DELAY = 1`, low concurrency, AutoThrottle
   enabled so Scrapy adapts to observed latency/errors.
3. Faster only if response codes and latency stay healthy — bans cost more than
   patience.

## Step 6 — Choose headers

1. If using Zyte API transparent mode: let it manage browser headers/cookies
   (sessions must look like ONE stable browser).
2. Otherwise copy the *semantic* headers from DevTools → Network → request →
   "Copy as cURL": `Accept`, `Accept-Language` — not the fingerprint soup.

## Step 7 — Verify cheaply before a paid run

- Offline tests: `python -m unittest discover -s tests -v` (no credits spent).
- One zip, `page_limit_per_zip = 1`, watch logs: pool ids, statuses, items.
- Then scale zips/pages.

Keep this file's checklist; it generalizes beyond Ralph Lauren.
