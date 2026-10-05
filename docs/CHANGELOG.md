# Changelog

Format: keep a new entry per work session — what changed and why. Update this
file whenever the code or docs change (see README for where things live).

## 2026-10-02 — v0.2.1 (zip codes configurable via .env)

- `ZIP_CODES=10001,90210,60601` in `.env` (and `.env.example`); settings.py
  parses it into a list; the spider picks it up in `from_crawler`.
- Precedence: `-a zip_codes=` CLI arg > `.env` ZIP_CODES > spider class
  default. All sources go through the same 5-digit validation.
- New `tests/test_spider.py` covers CLI override, single zip, invalid-zip
  ValueError, and default fallback (6 tests total, all offline).
- EXPLANATION.md fully synced to v0.2.1 code: page-objects strategy (CSS over
  stable hooks, constructor DI), session config without setLocation, .env
  zips, verified-selector table, updated run/troubleshooting sections, and a
  new **§8 "Every error and issue faced"** (13 items, symptom → cause → fix).

## 2026-10-02 — v0.2.0 (live-verified end to end)

**Goal reached**: items scraped per zip with real store-availability data.
Same sku, zip 10001 → NY stores; zip 90210 → Beverly Hills stores.

- **Architecture rework** after `setLocation` was rejected for this domain
  (`finish_reason=unsupported_set_location`): zip data now comes from the
  site's own SFCC endpoint `StoreInventory-Inventory?pid&zipCode=`, called
  inside each zip's session pool. PDP (once per product) is the source for
  price/name/description/images; tiles lazy-load prices, so listing tile
  prices are only a fallback.
- **Empirical discovery**: fetched live listing + PDP through the zyte-api
  client (saved under `debug/`), extracted real selectors
  (`data-pname`, `.price`, `h1.product-name`, `input.js-product-normal-prices`,
  `a.more-button`), and saved real fixtures under `tests/fixtures/`.
- **SessionConfig**: params → plain `browserHtml` (no setLocation), check →
  True; `ZYTE_API_SESSION_POOL_SIZE = 1` (one shopper per zip, fewer browser
  sessions burned).
- **Browser actions**: listing/PDP requests force `browserHtml` +
  `scrollBottom`. Learned the hard way: `scrollToBottom` and `waitFor{seconds}`
  are invalid — valid names are `scrollBottom`, `waitForSelector`,
  `waitForTimeout` (per Zyte docs).
- **Page-object DI fix**: `ItemPage` needs `def __init__(self, response:
  HttpResponse)` — deps are constructor-injected; assigning `page.response`
  only worked in tests, crashed in production.
- **USER_AGENT = ""**: `None` crashes RobotsTxtMiddleware (assert); "" passes
  robots matching but sends no UA header, so Zyte API sets a realistic one
  (ban-sensitive-header warnings gone).
- **Spider**: zip validation (`\d{5}`, raises on bad input — the earlier
  string-iteration bug produced zip pools "0"/"1"); listing now only crawled
  for zip[0]; PDP fans out inventory requests for all zips with full data
  attached (no cache races); `attrs.evolve` per-zip item copies.
- Validation pipeline now requires `url` + `name` (price optional in
  `fetch_pdp=False` cheap mode; CYO "customize" products dropped for missing
  name — correct behavior).
- EXPLANATION.md: flow diagram + zip-mechanism section rewritten to match the
  final design.
## 2026-10-02 — v0.1.1 (first-crawl fixes)

- **Bug**: first real crawl finished in 0.01s with zero requests. Cause:
  Scrapy 2.19's default `Spider.start()` reads only `start_urls` and no longer
  calls `start_requests()` (compat shim removed since the 2.13 `start()` API).
  Fix: spider now defines `async def start()` (note: `yield from` is illegal
  in async generators — plain loop).
- **Deprecations**: removed the `spider` argument from all
  middleware/pipeline hooks (`process_response`, `process_exception`,
  `process_item`, `open_spider`, `close_spider`); access via
  `from_crawler()` + `self.crawler` instead.
- Verified offline: `start()` yields the zip-tagged request; middleware and
  pipeline managers build with `ScrapyDeprecationWarning` escalated to error;
  unit tests pass.
- **Headers**: removed `DEFAULT_REQUEST_HEADERS` — first live crawl warned
  that user-set `Accept`/`Accept-Language` are "ban-sensitive" and hurt Zyte
  API's ban avoidance. Zyte manages all headers in transparent mode.
- **Sessions scoped per-request**: removed global `ZYTE_API_SESSION_ENABLED =
  True` — it pulled the automatic robots.txt fetch into session machinery
  (browser session + retries for a text file), the likely cause of a crawl
  hanging at `Crawled 0 pages` for 4+ minutes. The mixin's per-request meta
  opts in every zip request explicitly.
- **Start URL corrected**: search-indexed results show the men's clothing
  category is `https://www.ralphlauren.com/men-clothing` (pattern
  `/men-clothing`, not the guessed `/men-clothing-men`). Subcategories follow
  `/men-clothing-<type>` (e.g. `-suits`); `/men` is the hub page.
- Docs: EXPLANATION.md diagram and docs/03 updated to modern signatures;
  EXPLANATION.md §4.3 rewritten with the header lesson.

## 2026-10-02 — v0.1.0 (initial build)

- Project scaffolded manually (no `startproject`): scrapy.cfg, package layout,
  `.env`/`.env.example`, `.gitignore`.
- **Zyte API**: `scrapy_zyte_api.Addon` + `scrapy_poet.Addon`, transparent mode,
  key via `.env`.
- **Sessions**: `RalphLaurenSessionConfig` (`LocationSessionConfig`) registered
  with `@session_config`; per-zip pools `www.ralphlauren.com@US,<zip>`;
  `setLocation` init inherited.
- **Mixin**: `ZipCodeCrawlMixin` (`zip_meta` / `zip_requests` / `zip_follow`).
- **Page objects**: `ProductPage` (JSON-LD-first, CSS fallback), `ListingPage`
  (navigation). Registered via `@handle_urls`; imported from settings for
  registration order.
- **Middleware**: `ZipStatsMiddleware` (per-zip response/error stats, warns on
  HTTP ≥ 400).
- **Pipelines**: validation → (url, zip) dedupe → per-zip JSONL export.
- **Items**: `ZipProduct` = zyte-common-items `Product` + `zip_code`.
- **Tests**: offline page-object tests with fixture HTML (caught the `css`
  attribute shadowing bug and a URL-dedupe bug).
- **Discovery**: robots.txt fetched live (search & facets disallowed); direct
  site/sitemap fetch 307-redirects → documented as the reason for Zyte API.
  CSS selectors are SFCC-convention placeholders pending live verification
  (docs/07).
- Docs: EXPLANATION.md, README.md, docs/01–08, this changelog.

### Next
- [ ] Live-verify selectors (docs/07 workflow) with one zip, `page_limit_per_zip=1`
- [ ] Widen categories / zips after verification
