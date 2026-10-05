# 01 — Project structure

```
ralphlauren/                  ← project root (scrapy.cfg lives here)
├── scrapy.cfg                # tells Scrapy where settings live; deploy target
├── .env / .env.example       # ZYTE_API_KEY (never committed)
├── README.md                 # quickstart + file map
├── EXPLANATION.md            # THE full explanation document
├── docs/                     # one deep-dive per concept (this folder)
├── tests/                    # offline page-object tests (unittest)
├── output/                   # created at runtime; one .jsonl per zip
└── ralphlauren/              # the Python package
    ├── settings.py           # addons, politeness, pipelines, middlewares
    ├── items.py              # ZipProduct = zyte-common-items Product + zip_code
    ├── mixins.py             # ZipCodeCrawlMixin
    ├── middlewares.py        # ZipStatsMiddleware
    ├── pipelines.py          # validation / dedupe / per-zip export
    ├── session_configs.py    # RalphLaurenSessionConfig (@session_config)
    ├── page_objects/
    │   ├── product_page.py   # PDP extraction (ItemPage)
    │   └── listing_page.py   # listing navigation (WebPage)
    └── spiders/
        └── products.py       # crawl flow only — no extraction logic
```

## Design rule used throughout

**Crawl logic in the spider, extraction logic in page objects, cross-cutting
concerns in middlewares/pipelines, session policy in session_configs.**

If you want to change *where* we crawl → `spiders/products.py`.
If a selector broke → `page_objects/*_page.py` (`selectors` dict).
If output format changed → `pipelines.py`.
If session/zip behavior changed → `mixins.py` + `session_configs.py`.

## Why two nested `ralphlauren/` folders?

Standard Scrapy layout: the outer folder is the *project root* (run `scrapy`
commands here), the inner folder is the *Python package* that `scrapy.cfg`
points to (`ralphlauren.settings`). Imports everywhere are
`from ralphlauren.xxx import yyy`.
