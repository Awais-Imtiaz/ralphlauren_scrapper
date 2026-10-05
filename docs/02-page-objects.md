# 02 — Page Objects (`page_objects/`)

Libraries: **web-poet** (page object framework) + **scrapy-poet** (Scrapy glue /
dependency injection).

## The idea

Classic Scrapy tutorials put CSS/XPath inside spider callbacks. That couples
*navigation* with *extraction*, makes tests need the network, and duplicates
selectors across spiders. Page Objects fix that:

```
spider callback  →  "here's a ListingPage, give me the product URLs"
page object      →  owns ALL selectors/extraction for that page type
```

## The two kinds we use

| Class | Base | Purpose | Output |
|---|---|---|---|
| `ProductPage` | `ItemPage[ZipProduct]` | product detail fields | an item via `to_item()` |
| `ListingPage` | `WebPage` | navigation | `product_urls()`, `next_page_url()` |

## How injection works

1. `@handle_urls("www.ralphlauren.com")` registers the class in web-poet's
   rules registry (domain → page class).
2. `settings.py` imports `ralphlauren.page_objects` so registration happens
   before the crawler starts.
3. A callback declares a typed parameter:

```python
async def parse_product(self, response, product: ProductPage):
    item = await product.to_item()
```

4. **scrapy-poet** sees the annotation, builds a `ProductPage` wrapped around
   the response, and passes it in. `to_item()` is a coroutine (web-poet allows
   async fields), hence `async def` + `await` — Scrapy 2.19 supports coroutine
   callbacks natively.

## `@field` methods

Each `@field` method produces one item attribute. Missing data → return `None`;
the item schema (`zyte-common-items Product`) marks fields optional.

## JSON-LD first, CSS fallback

`ProductPage` prefers structured data (`<script type="application/ld+json">`)
because it's a *contract* platforms emit for SEO — far more stable than class
names. CSS is only the fallback. Real-world effect: even before selectors are
hand-verified on the live site, a PDP with JSON-LD extracts correctly.

## Gotcha we hit during the build

Naming a class attribute `css = {...}` **shadowed** the inherited `self.css()`
method from `WebPage` and crashed at runtime. Caught by the offline tests, fixed
by renaming to `selectors`. Two lessons: run `tests/` after touching page
objects; don't fight inherited namespaces.

## Testing offline

`tests/test_page_objects.py` feeds fixture HTML to each page object — no
network, no API credits, instant feedback while iterating on selectors.
