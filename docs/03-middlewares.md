# 03 — Middlewares (`middlewares.py`)

A middleware is a hook that sees **every request and/or response**. Use them for
cross-cutting concerns — things that must apply to all requests regardless of
which spider/callback produced them.

## Two kinds

- **Downloader middlewares** — between engine and downloader: modify requests
  before send, responses after receive, retry/flag failures.
- **Spider middlewares** — between engine and callbacks: process spider
  input/output (e.g. filtering offsite requests, handling DepthMiddleware).

Ours is a downloader middleware (`ZipStatsMiddleware`, priority **550**).

## What ours does

```python
def __init__(self, crawler):
    self.crawler = crawler          # from_crawler() passes the crawler in

def process_response(self, request, response):
    # inc_value("zip/10001/responses")  → per-zip counters in Scrapy stats
    # warn on HTTP >= 400                → per-zip error visibility
    return response

def process_exception(self, request, exception):
    # inc_value("zip/10001/errors")      → per-zip failure counting
    return None    # None = "I didn't handle it, let others see it"
```

> Note the **modern hook signatures** (Scrapy ≥ 2.13): the old `spider`
> argument is deprecated (2.19 warns, later versions drop it). Need the
> spider? Save the crawler in `from_crawler()` and use `self.crawler.spider`.

At the end of a run, `scrapy stats` prints e.g. `zip/10001/responses: 24`,
`zip/90210/errors: 1` — instantly answering *"which zip is misbehaving?"*

## Priority numbers (order in the chain)

`DOWNLOADER_MIDDLEWARES = {"ralphlauren.middlewares.ZipStatsMiddleware": 550}`

Scrapy merges ours with built-ins, sorted by priority. Reference points:

| Priority | Middleware |
|---|---|
| 100 | RobotsTxtMiddleware |
| 400 | DefaultHeadersMiddleware |
| 550 | **ZipStatsMiddleware (ours)** |
| 550–560 | HttpCompressionMiddleware, etc. |
| higher | downloader itself |

Lower = earlier on the way out, **later** on the way back. At 550 we see the
request nearly final (headers applied) and the response before decompression
cleanup — good for status-based stats.

## What we intentionally left out

No User-Agent rotation, no proxy header hacks, no manual cookies. In Zyte
transparent mode those are the API's job — and a *session* should look like one
stable browser, not a new fingerprint per request. Adding spoofing here would
actively break sessions.

The Zyte API plumbing itself (routing downloads through the API) is installed by
`scrapy_zyte_api.Addon` as a download handler + its own middlewares — composed,
not duplicated, by our middleware.
