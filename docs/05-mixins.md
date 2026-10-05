# 05 — Mixins (`mixins.py`)

A mixin is a class that adds one **capability** to another class through
inheritance, without being useful (or a full component) on its own.

## Our mixin: `ZipCodeCrawlMixin`

Gives any spider "zip-aware crawling" in one line of inheritance:

```python
class ProductsSpider(ZipCodeCrawlMixin, Spider):   # ← the capability
```

What it provides:

| Method | Used for |
|---|---|
| `zip_meta(zip_code)` | the meta dict that joins a request to the zip's Zyte session pool and tags it with the plain `zip_code` |
| `zip_requests(urls, cb)` | seed requests: every category × every zip |
| `zip_follow(url, zip, cb)` | follow a link **without leaving the current zip's session** |

The guarantee it enforces: *no request can accidentally lose its zip*. Every
request the spider makes goes through `zip_meta()`, so `response.meta["zip_code"]`
is always present for callbacks, the stats middleware, and the export pipeline.

## Why a mixin instead of a base class?

If zip-ness lived in `class ZipSpider(Spider)`, then a spider needing BOTH
crawl-rules (`CrawlSpider`) and zips would be stuck — Python has single
inheritance for that axis. As a mixin:

```python
class BigSpider(ZipCodeCrawlMixin, CrawlSpider): ...   # composes freely
```

MRO (`ZipCodeCrawlMixin` first) means the mixin's helpers win; it deliberately
defines **no** Spider lifecycle methods, so it never fights the host class.

## Why plain `meta["zip_code"]` AND the `zyte_api_session_location` meta?

Two different consumers:
- `zip_code` — ours: callbacks read it, `ZipStatsMiddleware` counts it,
  `PerZipCodeExportPipeline` routes by it.
- `zyte_api_session_location` — scrapy-zyte-api's: `SessionConfig.pool()` reads
  it to build the `www.ralphlauren.com@US,<zip>` pool id.

Keeping them as two keys keeps our logic decoupled from the API's internals.
