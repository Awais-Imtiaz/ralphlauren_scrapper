import json
from pathlib import Path

from attrs import asdict
from scrapy.exceptions import DropItem


class ProductValidationPipeline:
    required_fields = ("url", "name")  # price may be absent in cheap mode (lazy tiles)

    def process_item(self, item):
        missing = [f for f in self.required_fields if getattr(item, f, None) is None]
        if missing:
            raise DropItem(f"missing {missing}: {getattr(item, 'url', None)}")
        return item


class DuplicateFilterPipeline:
    def open_spider(self):
        self.seen = set()

    def process_item(self, item):
        key = (item.url, item.zip_code)
        if key in self.seen:
            raise DropItem(f"duplicate in {item.zip_code}: {item.url}")
        self.seen.add(key)
        return item


class PerZipCodeExportPipeline:
    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def open_spider(self):
        self.dir = Path(self.crawler.settings.get("OUTPUT_DIR", "output"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files: dict = {}

    def process_item(self, item):
        fh = self.files.get(item.zip_code)
        if fh is None:
            fh = (self.dir / f"{item.zip_code}.jsonl").open("w", encoding="utf-8")
            self.files[item.zip_code] = fh
        fh.write(json.dumps(asdict(item), ensure_ascii=False, default=str) + "\n")
        return item

    def close_spider(self):
        for fh in self.files.values():
            fh.close()
