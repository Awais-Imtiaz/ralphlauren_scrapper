# EXPLANATION — the full story of this scraper

This document explains **everything**: what each piece does, where every concept
lives, why decisions were made, and — most importantly — **how I knew what to
write**: which URL to start from, which delay to use, which headers to set.
The reusable methodology is in [docs/07-discovery-method.md](docs/07-discovery-method.md);
this file applies it to this project.

---

## 1. What this scraper does

Goal: for a list of US zip codes, scrape Ralph Lauren product data (name, price,
availability signals, sku, description, images) **as the site shows it in that
zip code**.

The zip problem is the interesting part. Sites vary content by location through a
mix of: IP geolocation, cookies set by a "delivery location" modal, and URL
parameters. Faking only a cookie often doesn't work because the server also
checks the client IP's geography.

**Our approach** (final, live-verified): Ralph Lauren's zip variation is
**store availability** — the site exposes a Salesforce Commerce Cloud endpoint,
`StoreInventory-Inventory?pid=<product>&zipCode=<zip>`, returning store-by-store
stock around that zip. The spider calls it per (product × zip), each call inside
that zip's own Zyte API session pool (sticky IP + cookie jar per zip).
Product fields (name/price/description) come from the PDP via a page object.

**Journey note**: we first tried Zyte API's `setLocation` action to geolocate
whole sessions — the API rejected it for this domain
(`finish_reason=unsupported_set_location`), which led to discovering the
inventory endpoint by reading the page's embedded JS config. A real-world
scraper lesson: read the target's own frontend config; it documents the API for
you.

---

## 2. The request lifecycle (how all the concepts connect)

```
ProductsSpider.start()            ← async, the Scrapy ≥2.13 API
  │  listing request (browserHtml + scrollBottom) in zip[0]'s session
  │  ZipCodeCrawlMixin.zip_meta() adds:
  │    zip_code, zyte_api_session_enabled=True,
  │    zyte_api_session_location={addressCountry: US, postalCode: <zip>}
  ▼
Engine → Downloader middleware chain
  │  ZipStatsMiddleware (ours, 550): counts responses per zip, logs HTTP ≥ 400
  │  (+ built-ins: robots.txt check, retries, …)
  ▼
scrapy-zyte-api download handler (transparent mode: EVERY request goes
  through Zyte API instead of a direct connection)
  │  SessionConfig.pool() sees the location meta
  │  → pool id "www.ralphlauren.com@US,<zip>", one sticky session each
  │  Session init: plain browserHtml (setLocation unsupported here)
  ▼
parse_listing(response, listing: ListingPage)        [scrapy-poet injection]
  │  listing.product_entries() → pid/name/url from .product-tile data attrs
  │  → PDP request per product (browserHtml, once — not per zip)
  ▼
parse_product(response, product: ProductPage)
  │  item = await product.to_item()   # name/price/sku/description/images
  │  → fans out, for EVERY zip: StoreInventory-Inventory?pid&zipCode=<zip>
  │    (cheap raw-HTTP request inside that zip's own session pool)
  ▼
parse_availability → attrs.evolve(item, zip_code=…, stores=…, in_stock_count=…)
  ▼
Item pipelines, in order:
  │  100 ProductValidationPipeline   → DropItem if url/name missing
  │  200 DuplicateFilterPipeline     → DropItem if (url, zip) already scraped
  │  300 PerZipCodeExportPipeline    → append to output/<zip>.jsonl
  ▼
output/10001.jsonl, output/90210.jsonl … (verified live: same product,
different store sets per zip)
```

---

## 3. Where each concept lives and why

### 3.1 Page Objects — `ralphlauren/page_objects/`

**What**: classes that own *extraction* logic for a page type. The spider only
decides *what to visit*; page objects decide *how to read* a page.

**Why**:
- The spider stays tiny and readable (see `parse_product` — 3 lines).
- Extraction can be unit-tested offline with fixture HTML — that's exactly what
  `tests/test_page_objects.py` does, no network, no API credits.
- Selectors live in one place per page type (`selectors` dict at the top).

**How they work**: `@handle_urls("www.ralphlauren.com")` registers the class in
web-poet's rules registry. When a callback declares a parameter annotated with a
page-object type (`listing: ListingPage`), **scrapy-poet** builds it for you and
passes it in (dependency injection). `ItemPage.to_item()` (a coroutine, hence
`async def` callbacks) assembles the item from `@field` methods.

Two flavors here:
- `ProductPage(ItemPage[ZipProduct])` — an *item* page: outputs an item.
  Important web-poet detail: `ItemPage` subclasses receive their dependencies
  via the **constructor** — `def __init__(self, response: HttpResponse)` —
  not via an auto-assigned attribute.
- `ListingPage(WebPage)` — navigation **and** tile extraction:
  `product_entries()` reads `data-pname` / `data-itemid` attributes and
  `.price` from each `.product-tile`, plus the `a.more-button` next-page link.

`settings.py` imports `ralphlauren.page_objects` purely for registration
side-effects (`# noqa: F401`) — decorators must run before the crawler starts.

**Strategy note — why plain CSS**: the plan started as "JSON-LD first"
(structured data is a stabler contract than class names), but the live PDPs
turned out to carry only Organization/WebSite/WebPage JSON-LD — no `Product`.
So extraction uses CSS over *stable* hooks instead: `data-*` attributes,
`js-product-*` hidden inputs, and meta tags — all verified against real
captured pages, with real fixtures in `tests/fixtures/`.

### 3.2 Pipelines — `ralphlauren/pipelines.py`

Pipelines process every item *after* the callback yields it. Ordered by the
numbers in `ITEM_PIPELINES` (settings.py):

1. `ProductValidationPipeline` (100) — drops items missing `url`, `name` or
   `price` via `DropItem`. Garbage in, garbage out — so filter early.
2. `DuplicateFilterPipeline` (200) — a set of `(url, zip_code)` keys; the same
   product can legitimately appear under several zips, but twice under one zip
   is a bug or a pagination loop.
3. `PerZipCodeExportPipeline` (300) — opens `output/<zip>.jsonl` lazily on first
   item, appends one JSON line per item (`attrs.asdict` serializes our item
   class), closes files in `close_spider`. One file per zip = trivially
   comparable across zips.

Lifecycle hooks used: `open_spider`, `process_item`, `close_spider`.

### 3.3 Middlewares — `ralphlauren/middlewares.py`

Middlewares sit between the engine and the downloader (downloader middlewares)
or between the engine and spider callbacks (spider middlewares). They see *every
request/response* — the right layer for cross-cutting concerns.

Ours: `ZipStatsMiddleware` (downloader middleware, priority 550):
- `process_response` — increments `zip/<zip>/responses` in Scrapy stats and
  warns on HTTP ≥ 400 (visible in the end-of-run stats dump: did one zip fail
  while others worked?).
- `process_exception` — counts `zip/<zip>/errors` when a download dies.

Priority 550 places it after the built-in middleware stack (robots.txt 100,
default headers 400, etc.) but before the downloader — meaning it sees the
request as finally shaped. The Zyte API magic itself is wired by the
`scrapy_zyte_api.Addon`, which installs its own download handler/middlewares —
we don't reimplement that, we compose with it.

Note what we deliberately did **not** do here: no fake `User-Agent` rotation, no
manual cookie injection. In transparent mode Zyte API manages browser-realistic
headers and cookies per session; doing it ourselves would *break* the sessions.

### 3.4 Mixins — `ralphlauren/mixins.py`

A mixin is a small class providing reusable behavior, composed into a spider via
inheritance without being a spider itself.

`ZipCodeCrawlMixin` gives any spider three things:
- `zip_meta(zip_code)` — the request meta that (a) tags the request with the
  plain `zip_code` (so callbacks/pipelines can read it) and (b) joins the
  per-zip Zyte session pool (`zyte_api_session_enabled` +
  `zyte_api_session_location`).
- `zip_requests(urls, callback)` — seeds: category × zip cross-product.
- `zip_follow(url, zip_code, callback)` — follows a URL *staying in the same
  zip's session*.

Why a mixin and not a base class? `ProductsSpider(ZipCodeCrawlMixin, Spider)`
— you can later mix it into a `CrawlSpider`, an XMLFeedSpider, etc. It's the
"zip awareness" capability, decoupled from crawl logic.

### 3.5 ZyteSessionConfig — `ralphlauren/session_configs.py`

`scrapy-zyte-api` (v0.36) exposes `SessionConfig` and the
`@session_config(["www.ralphlauren.com"])` decorator, which registers *the*
session policy for a domain. Our final config:

```python
@session_config(["www.ralphlauren.com"])
class RalphLaurenSessionConfig(SessionConfig):
    def params(self, request):
        return {"browserHtml": True}   # plain warm-up, NO setLocation

    def check(self, response, request):
        return True
```

What each piece does:

- `pool(request)` (inherited) — still reads the `zyte_api_session_location`
  meta from the mixin → pool id `www.ralphlauren.com@US,<zip>` → **one sticky
  session per zip** (own IP + cookie jar for that zip's inventory calls).
- `params()` — the session *initialization* request. The default would add a
  `setLocation` browser action to geolocate the session to the zip; Zyte API
  rejected it for this domain (`finish_reason=unsupported_set_location`), so
  sessions warm up with a plain `browserHtml` request instead. The zip now
  enters explicitly through the StoreInventory endpoint's `zipCode` parameter
  (see the spider).
- `check()` — nothing to validate anymore (no actions), so sessions are kept.
- `ZYTE_API_SESSION_POOL_SIZE = 1` (settings) — one session per pool: one
  "shopper" per zip, and far fewer paid browser sessions than the default 8.

### 3.6 Zyte API (free tier) — `settings.py` + `.env`

- **Key & zips**: create an account at app.zyte.com → API keys → paste into
  `.env`. The same file now also holds `ZIP_CODES=10001,90210,60601` — the
  spider reads it via settings (a `-a zip_codes=` CLI arg overrides it for one
  run). `settings.py` loads `.env` with python-dotenv; `.gitignore` keeps it
  out of the repo.
- **Transparent mode**: the `scrapy_zyte_api.Addon` (priority 500, after
  `scrapy_poet.Addon` at 400 — order matters) sets `ZYTE_API_TRANSPARENT_MODE`,
  so *every* request is transparently routed through Zyte API. No special code
  in the spider.
- **Why we need it at all**: this site returns HTTP 307 redirects to plain
  datacenter requests (verified while building this — even `robots.txt`'s
  sitemap redirected). Zyte API provides residential-grade sessions and
  browser rendering that get through.
- **Free-tier budgeting** (important while practicing):
  - `page_limit = 1` in the spider caps listing pages (listings are only
    crawled for the first zip; other zips only run cheap inventory calls).
  - `-a fetch_pdp=False` — skips the browser-rendered product pages entirely
    (tile data only, prices missing).
  - Start with ONE zip in `.env` while testing.
  - `CONCURRENT_REQUESTS_PER_DOMAIN = 2`, `DOWNLOAD_DELAY = 1.0`, AutoThrottle
    on — fewer parallel requests = slower burn + fewer blocks.
  - Each zip pool warms one browser session (`POOL_SIZE = 1`); PDPs are the
    main cost driver (one browser request each).

---

## 4. How I knew what to write (URLs, delays, headers, selectors)

You asked exactly the right question. Here's the honest answer, item by item.

### 4.1 The URLs

1. **robots.txt first** — always. `https://www.ralphlauren.com/robots.txt`
   (fetched live while building this) says:
   - `*/search*` is disallowed → don't crawl via search pages.
   - facet/sort params (`*prefn1*`, `*srule*`, `*pmin*`…) are disallowed →
     use **clean category URLs**, no query-string filters.
   - No `Crawl-delay` directive → politeness is our choice (see 4.2).
   `ROBOTSTXT_OBEY = True` enforces this automatically at crawl time too.
2. **Category URL** — taken from a browser: open ralphlauren.com → Men → copy
   the address bar (`https://www.ralphlauren.com/men-clothing-men`). The slug
   pattern (`-men` suffix) tells us it's Salesforce Commerce Cloud, which also
   informed the selector conventions (`.product-tile`, `a.thumb-link`).
3. **Sitemap** — robots.txt points at a sitemap index; it 307-redirects our
   direct requests (bot protection). With Zyte API it would be reachable and
   could seed deeper crawls — listed as a next step.

### 4.2 The delays

No `Crawl-delay` in robots.txt, so politeness is judgment + convention:

- `DOWNLOAD_DELAY = 1.0` — one request per second per slot is the common
  starting courtesy for a single-target crawl.
- `AUTOTHROTTLE_*` — lets Scrapy *adapt* instead of using a fixed guess: it
  watches response latency and error rates and backs off automatically. Target
  concurrency 2 keeps free-tier credits burning slowly.
- `CONCURRENT_REQUESTS_PER_DOMAIN = 2` — with 3 zip sessions in parallel we
  still only put 2 requests in flight at once per domain.
- Sessions add their own pacing (`ZYTE_API_SESSION_DELAY`, default 2s per
  pool) — sticky sessions must not be used too fast or the target flags them.

Rule of thumb: start slow, watch the response codes in the logs, only speed up
if the site is comfortable.

### 4.3 The headers

- With Zyte API transparent mode, **headers are Zyte's job** — it sends
  browser-consistent headers matching the session. Hand-rolling
  `User-Agent` rotation here would fight the session mechanism (a session
  should look like ONE stable browser, not a new one every request).
- **First-run lesson**: we initially set `DEFAULT_REQUEST_HEADERS`
  (`Accept`, `Accept-Language`) for content negotiation. The very first crawl
  warned: *"sends ban-sensitive header Accept to Zyte API … user-defined
  values can negatively impact ban avoidance effectiveness"* — so even
  well-meaning headers were removed. Zyte API handles all of it.
- No manual cookies, ever, in session mode — the session's cookie jar is the
  whole point.

### 4.4 The selectors (now verified against live pages)

The selectors started as **educated placeholders** — this machine gets a 307
bot-check from the site, so I couldn't see real HTML. Instead of guessing
forever, the pages were fetched *through Zyte API itself* (two one-off requests
with the `zyte-api` client, saved under `debug/`), and the selectors were
rewritten from the real markup:

| Data | Selector | Found how |
|---|---|---|
| Listing tile | `.product-tile` | SFCC convention, confirmed live |
| Product name (tile) | `@data-pname` attribute | real tile markup |
| Product id (tile) | `@data-itemid` (`"…-P"` suffix stripped) | real tile markup |
| Tile price | `.price ::text` (only ~3/72 tiles — lazy-loaded!) | real tile markup |
| Next page | `a.more-button::attr(href)` → `?page=2` | real pagination |
| PDP name | `h1.product-name::text` | real PDP |
| PDP price | `input.js-product-normal-prices::attr(value)` → `"74.99 - 118.0"` | real PDP hidden inputs |
| PDP sku | `input.js-product-rec-pid::attr(value)` | real PDP hidden inputs |
| PDP description / image | `meta[name=description]` / `meta[property=og:image]` | real PDP head |

Real fragments of those captures live in `tests/fixtures/` and drive the offline
tests — so selector regressions are caught without spending credits. The
reusable workflow (for this or any site) is [docs/07](docs/07-discovery-method.md).

### 4.5 The zip mechanism (final: live-verified)

The first idea was Zyte API sessions + `setLocation` (browser geolocation per
zip). The API rejected it for ralphlauren.com — `setLocation` only works on
Zyte-supported domains. So we read the site's own frontend config (embedded
`URLs` JS object in the page source) and found the real mechanism:

```
StoreInventory-Inventory?pid=<productId>&zipCode=<zip>   → store-level stock
StoreInventory-SetZipCode / GetZipCode                   → session zip state
Stores-FindInStore                                       → store search
```

Probing `Inventory?pid=401480&zipCode=10001` returned live store JSON for
Manhattan. Decision matrix, as actually lived:
- `setLocation` sessions — ✗ unsupported on this domain
- Site zip cookie / `SetZipCode` endpoint — needs POST + CSRF surgery; fragile
- `Inventory?pid&zipCode` — ✓ plain GET, cheap, exact per-zip data → chosen

Sessions remain valuable: each zip's inventory calls run in their own sticky
session pool (`www.ralphlauren.com@US,<zip>`), so cookies/IP stay consistent
per zip — the same shape a real shopper's session would have.

---

## 5. How to run

Zip codes live in `.env` (`ZIP_CODES=10001,90210,60601`):

```bash
cd "/home/awais/Scrapping practice" && source .venv/bin/activate && cd ralphlauren
scrapy crawl products                            # zips from .env, PDP data
scrapy crawl products -a fetch_pdp=False         # cheap mode (no browser PDPs)
scrapy crawl products -a zip_codes=33101         # one-off override
scrapy crawl products -s CLOSESPIDER_ITEMCOUNT=5 # stop early while learning
```

Watch the logs for: session pool ids (`www.ralphlauren.com@US,10001`), per-zip
stats (`zip/10001/responses`), and pipeline drops. Results land in
`output/<zip>.jsonl`, one JSON object per (product × zip):

```json
{"name": "Faux-Fur-Trim Fleece Jacket", "price": "74.99", "currency": "USD",
 "sku": "100096437", "url": "https://…", "description": "…", "images": […],
 "zip_code": "10001", "in_stock_count": 0,
 "stores": [{"storeId": "8044", "city": "New York", "quantity": 0, …}]}
```

## 6. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| 401/403 from Zyte API | missing/wrong key in `.env` |
| `zip codes must be 5 digits` ValueError | bad `ZIP_CODES` in `.env` or `-a` arg |
| "Action setLocation not supported" | historical — this domain doesn't support it; the scraper no longer uses it |
| One zip fails, others fine | that session was flagged → re-run; sessions auto-reinit |
| Credits gone fast | `-a fetch_pdp=False`, lower `page_limit`, fewer zips, keep AutoThrottle on |
| 400 "Format of field actions[0] is invalid" | action name wrong — valid: `scrollBottom`, `waitForSelector`, `waitForTimeout` |

## 7. Next steps

- Widen: more `category_urls`, more zips in `.env`, higher `page_limit`.
- Try `AutoProductPage` from zyte-common-items (AI extraction, zero selectors)
  as a comparison run.
- Compare zips: `jq -s` over the JSONL files (e.g. which stores stock an item
  in both 10001 and 90210).
- Deploy to Scrapy Cloud (Zyte) when local runs feel small.

---

## 8. Every error and issue faced, and how each was solved

The build hit **real** problems — that's normal for scraping. Each one below is
a lesson, in the order it happened. (Also see `docs/CHANGELOG.md` for the same
history in commit-log form.)

### 8.1 Spider exited instantly — zero requests

- **Symptom**: first `scrapy crawl` logged "Spider opened" → "Closing spider
  (finished)" in 0.01s with no requests. No error.
- **Cause**: Scrapy 2.13+ replaced `start_requests()` with `async def start()`.
  By Scrapy 2.19 the compatibility shim is gone — the default `start()` only
  reads `start_urls`, which we don't use.
- **Fix**: `async def start(self)` in the spider. (Detail: `yield from` is a
  `SyntaxError` inside async generators — use a plain `for` loop.)

### 8.2 Deprecation warnings on every hook

- **Symptom**: `…requires a spider argument, this is deprecated…` for all
  middleware/pipeline methods.
- **Cause**: Scrapy is removing the `spider` parameter from hooks.
- **Fix**: dropped `spider` args everywhere; classes that need context take the
  crawler via `from_crawler()` and use `self.crawler` / `self.crawler.spider`.

### 8.3 "Ban-sensitive header" warnings

- **Symptom**: every request warned about `Accept` / `Accept-Language`.
- **Cause**: our `DEFAULT_REQUEST_HEADERS` — in transparent mode Zyte API
  generates better browser headers itself, and user-set ones weaken ban
  avoidance.
- **Fix**: removed the setting entirely; later also `USER_AGENT = ""` (§8.7).

### 8.4 Wrong start URL (guessed)

- **Symptom**: would have crawled a nonexistent page.
- **Cause**: the category URL was a guess from URL conventions.
- **Fix**: verified real category URLs via web search (`/men-clothing`, not
  `/men-clothing-men`). Lesson: ground every URL in evidence.

### 8.5 Crawl hung at `Crawled 0 pages` for 4+ minutes

- **Symptom**: LogStats heartbeats, zero pages, silence.
- **Cause**: `ZYTE_API_SESSION_ENABLED = True` **globally** — even the
  automatic `robots.txt` fetch was pulled into session machinery (a browser
  session just to read a text file), stuck in init retries.
- **Fix**: sessions opt in per request via the mixin's meta
  (`zyte_api_session_enabled: True`). The very next run fetched robots.txt in
  7 seconds.

### 8.6 `setLocation` unsupported on this domain

- **Symptom**: `ERROR: Stopping the spider, tried to use the setLocation action
  on an unsupported website` → `finish_reason=unsupported_set_location`.
- **Cause**: Zyte's geolocation action works only on Zyte-supported domains;
  ralphlauren.com isn't one.
- **Fix**: the biggest pivot of the project. Read the site's embedded JS
  config, found its own endpoints, and probed
  `StoreInventory-Inventory?pid&zipCode=` → live per-zip store JSON. Sessions
  stay (one pool per zip); the zip enters as an explicit URL parameter.

### 8.7 `USER_AGENT = None` crashed robots checking

- **Symptom**: `AssertionError` in `robotstxt.py: assert useragent is not None`.
- **Cause**: robots.txt matching is per-user-agent; Scrapy asserts one exists
  when `ROBOTSTXT_OBEY` is on.
- **Fix**: `USER_AGENT = ""` — passes the robots machinery (matches as `*`)
  while sending no UA header, so Zyte API supplies a realistic one.

### 8.8 Zip codes iterated as characters

- **Symptom**: stats showed `zip/0/responses` and `zip/1/responses` — pools
  for the *characters* "1" and "0" instead of "10001".
- **Cause**: `-a zip_codes=10001` passes a string; a rewrite of the spider
  dropped the `.split(",")` handling, so `for zip_code in "10001"` yielded
  characters.
- **Fix**: centralized `_set_zip_codes()` with `re.fullmatch(r"\d{5}")`
  validation that raises on bad input — this class of silent bug can't recur.

### 8.9 web-poet `ItemPage` needs constructor injection

- **Symptom**: `AttributeError: 'ProductPage' object has no attribute
  'response'` — in production, while offline tests passed!
- **Cause**: my tests assigned `page.response = …` manually; scrapy-poet
  actually injects dependencies through `__init__(self, response:
  HttpResponse)`.
- **Fix**: declared the constructor. **Meta-lesson**: test objects through the
  same construction path production uses, or the test lies to you.

### 8.10 Invalid browser action formats

- **Symptom**: `400 … "Format of field actions[0] is invalid"`, then
  `"unrecognized property state"`.
- **Cause**: guessed action names/fields — `scrollToBottom`, `waitFor` with
  `seconds`, `waitForSelector` with `state`.
- **Fix**: checked the docs: valid names are `scrollBottom`, `waitForSelector`
  (no `state`), `waitForTimeout`. Guessed-and-prayed cost ~4 paid requests;
  reading docs first would have cost zero.

### 8.11 Tile prices lazy-loaded (only 3/72 render)

- **Symptom**: 22–92 items dropped as `missing ['price']`.
- **Cause**: Ralph Lauren tiles render prices via JS only when each tile
  scrolls into view; even `scrollBottom` + `waitForSelector` left most empty
  (no price data exists in the DOM/JSON at all until per-tile JS runs).
- **Fix**: architecture flip — the PDP is the price source (always rendered),
  fetched once per product; the listing only supplies pid/name/url. Validation
  relaxed to `url` + `name`; a `fetch_pdp=False` cheap mode accepts missing
  prices.

### 8.12 Credit burn: 16 browser sessions per run

- **Symptom**: `request_args/browserHtml: 16` for a tiny crawl.
- **Cause**: default `ZYTE_API_SESSION_POOL_SIZE` is 8, and pools existed for
  the two accidental char-zips.
- **Fix**: pool size 1 (one shopper per zip — also conceptually right).

### 8.13 Small stuff worth remembering

- `find_dotenv()` crashes in `python - <<EOF` scripts (no file frame) — pass
  the `.env` path explicitly.
- web-poet's `urljoin` returns `RequestUrl` objects that don't hash-equal —
  `str()` them before deduping.
- A class attribute named `css` shadows `WebPage.css()` — caught by offline
  tests; renamed to `selectors`.
- The zyte-api client's `get()` returns a plain dict — `httpResponseBody` is
  base64 and there is no `.api_response` attribute (my probe script, not the
  API, was broken).

**The pattern across all of it**: every failure had a *named* signal (a log
line, a stat, a status code). Escalate logging (`-s LOG_LEVEL=DEBUG`), read
the actual error, verify assumptions with one cheap probe — then fix the code,
and write the lesson down so it isn't paid for twice.
