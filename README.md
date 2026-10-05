# Ralph Lauren Scraper — products by ZIP code

Scrapes product data from `www.ralphlauren.com` **per US zip code**, using
Zyte API sticky sessions, so availability matches each zip's stores.

Built with: Scrapy + scrapy-poet (Page Objects) + web-poet + scrapy-zyte-api
(sessions) + zyte-common-items (Product schema).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your ZYTE_API_KEY into .env
scrapy crawl products                            # zips come from .env ZIP_CODES
scrapy crawl products -a zip_codes=10001,33101   # one-off override (wins over .env)
scrapy crawl products -a fetch_pdp=False         # cheap mode (no browser PDPs)
```

**Zip codes are configured in `.env`** (`ZIP_CODES=10001,90210,60601`) — edit,
run, done. A `-a zip_codes=` CLI argument overrides `.env` for one run.

Output: one JSONL file per zip in `output/` (e.g. `output/10001.jsonl`) —
each item carries product fields plus `stores` (store-level availability for
that zip) and `in_stock_count`.

## How it works

```
listing (browserHtml + scrollBottom, first zip's session)
  └─ product tiles -> one PDP per product (browserHtml; price/desc/images
                      source — tiles lazy-load prices)
       └─ StoreInventory-Inventory?pid=<pid>&zipCode=<zip>
          inside each zip's own session pool
          -> output/<zip>.jsonl
```

Zip scoping rides on two things: Ralph Lauren's SFCC platform exposes a
public store-inventory endpoint that takes the zip as a query parameter,
and every request joins a per-zip Zyte API session pool
(`www.ralphlauren.com@US,<zip>`), so cookies/headers stay consistent per
zip. `setLocation` is NOT used — ralphlauren.com rejects that action;
warm-up is a plain browserHtml request instead.

## File map

| File | Concept | Role |
|---|---|---|
| `ralphlauren/spiders/products.py` | — | crawl flow: listing → products, per zip |
| `ralphlauren/page_objects/product_page.py` | **Page Objects** | PDP field extraction (stable hooks, no JSON-LD on this site) |
| `ralphlauren/page_objects/listing_page.py` | **Page Objects** | listing navigation (product links, next page) |
| `ralphlauren/pipelines.py` | **Pipelines** | validation → dedupe → per-zip JSONL export |
| `ralphlauren/middlewares.py` | **Middlewares** | per-zip response stats + error logging |
| `ralphlauren/mixins.py` | **Mixins** | tags every request with a per-zip Zyte session |
| `ralphlauren/session_configs.py` | **ZyteSessionConfig** | sticky session pool per zip |
| `ralphlauren/items.py` | Zyte common items | `Product` schema + `zip_code` field |
| `ralphlauren/settings.py` | **Zyte API** | addons, transparent mode, politeness limits |

## Status

**Live-verified**: items scraped for zips 10001 & 90210 with different
store sets per zip for the same product. Selectors were derived from real
captured pages.

Note: prices only render on PDPs (tiles lazy-load them) — `fetch_pdp=False`
mode trades price coverage for cost.
