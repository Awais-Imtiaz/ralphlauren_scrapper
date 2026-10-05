# 04 — Pipelines (`pipelines.py`)

Pipelines process **items** after a callback yields them. Chain order = the
numbers in `settings.py`:

```python
ITEM_PIPELINES = {
    "ralphlauren.pipelines.ProductValidationPipeline": 100,
    "ralphlauren.pipelines.DuplicateFilterPipeline": 200,
    "ralphlauren.pipelines.PerZipCodeExportPipeline": 300,
}
```

## 1. ProductValidationPipeline (100) — quality gate

```python
missing = [f for f in ("url", "name", "price") if getattr(item, f, None) is None]
if missing: raise DropItem(...)
```

Fail fast: an item without name/price is noise, and dropping it *before*
dedupe/export keeps files clean. `DropItem` is Scrapy's idiomatic "reject this
item" exception — it's logged and counted (`item_dropped_count`), not a crash.

## 2. DuplicateFilterPipeline (200) — memory guard

Key = `(item.url, item.zip_code)`. The same product under *different* zips is
valid data (that's the whole point); the same (product, zip) twice means a
pagination loop or a repeated link. A `set` in RAM — fine at practice scale;
swap for Redis if this ever grows.

## 3. PerZipCodeExportPipeline (300) — output

- `open_spider` — create `output/`.
- `process_item` — lazily open `output/<zip>.jsonl` on first item for that zip,
  append `json.dumps(attrs.asdict(item))`.
- `close_spider` — close file handles.

Why JSONL (one JSON object per line) and not one big JSON array: appendable
without parsing the file, streamable, and `jq`/pandas read it line-by-line.

Why `attrs.asdict`: `ZipProduct` is an attrs class, and `asdict` recurses into
nested attrs objects (`Brand`, `Image`) — `dataclasses.asdict` wouldn't.

## Why not Scrapy's built-in FEED exports?

`scrapy crawl -o out.json` writes ONE file for all items. We want **one file
per zip code** — items routed by a field — which is exactly the case where a
custom pipeline is the clean solution.
