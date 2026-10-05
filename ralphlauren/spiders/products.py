import re
from collections import defaultdict

import attrs
from scrapy import Request, Spider

from ralphlauren.mixins import ZipCodeCrawlMixin
from ralphlauren.items import ZipProduct
from ralphlauren.page_objects.listing_page import ListingPage
from ralphlauren.page_objects.product_page import ProductPage

INVENTORY_URL = (
    "https://www.ralphlauren.com/on/demandware.store/"
    "Sites-RalphLauren_US-Site/en_US/StoreInventory-Inventory"
)

# Tiles lazy-load prices, so listing/PDP need a browser render + scroll.
BROWSER_PARAMS = {"browserHtml": True, "actions": [{"action": "scrollBottom"}]}


class ProductsSpider(ZipCodeCrawlMixin, Spider):
    """Products with store availability per zip code.

    Flow: listing (browserHtml + scroll, first zip's session) -> PDP once per
    product -> StoreInventory?pid=<pid>&zipCode=<zip> inside each zip's own
    session. Product fields don't vary by zip; the zip-varying part is store
    availability. Prices only render on PDPs (tiles lazy-load them), so with
    fetch_pdp=True the PDP is the data source; tile data is the cheap fallback.
    """

    name = "products"

    zip_codes = ["10001", "90210", "60601"]
    category_urls = ["https://www.ralphlauren.com/men-clothing"]
    page_limit = 1
    fetch_pdp = True
    max_stores_per_item = 5

    def __init__(self, *args, zip_codes=None, fetch_pdp=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._zips_from_cli = zip_codes is not None
        if zip_codes is not None:
            self._set_zip_codes(zip_codes)
        if fetch_pdp is not None:
            self.fetch_pdp = str(fetch_pdp).lower() not in ("0", "false", "no")
        self.pages_seen = defaultdict(int)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        if not spider._zips_from_cli:
            spider._set_zip_codes(crawler.settings.getlist("ZIP_CODES") or cls.zip_codes)
        return spider

    def _set_zip_codes(self, zip_codes):
        zips = zip_codes if isinstance(zip_codes, list) else zip_codes.split(",")
        bad = [z for z in zips if not re.fullmatch(r"\d{5}", z)]
        if bad:
            raise ValueError(f"zip codes must be 5 digits, got: {bad}")
        self.zip_codes = zips

    async def start(self):
        for url in self.category_urls:
            yield self.browser_request(url, self.zip_codes[0], self.parse_listing)

    def browser_request(self, url, zip_code, callback, **kwargs):
        request = self.zip_follow(url, zip_code, callback, **kwargs)
        request.meta["zyte_api"] = BROWSER_PARAMS
        return request

    async def parse_listing(self, response, listing: ListingPage):
        self.pages_seen[response.meta["zip_code"]] += 1

        for entry in listing.product_entries():
            if self.fetch_pdp:
                yield self.browser_request(
                    entry["url"], self.zip_codes[0], self.parse_product,
                    cb_kwargs={"entry": entry},
                )
            else:
                for zip_code in self.zip_codes:
                    yield self.inventory_request(entry, zip_code)

        if self.pages_seen[response.meta["zip_code"]] < self.page_limit:
            if next_url := listing.next_page_url():
                yield self.browser_request(
                    next_url, self.zip_codes[0], self.parse_listing
                )

    async def parse_product(self, response, product: ProductPage, entry):
        item = await product.to_item()
        item.url = entry["url"]
        for zip_code in self.zip_codes:
            yield self.inventory_request(entry, zip_code, pdp=item)

    def inventory_request(self, entry, zip_code, pdp=None):
        return Request(
            f"{INVENTORY_URL}?pid={entry['pid']}&zipCode={zip_code}",
            callback=self.parse_availability,
            meta=self.zip_meta(zip_code),
            cb_kwargs={"entry": entry, "pdp": pdp},
        )

    async def parse_availability(self, response, entry, pdp):
        stores = response.json()[: self.max_stores_per_item]
        in_stock = sum(1 for s in stores if s.get("quantity", 0) > 0)
        item = attrs.evolve(
            pdp or ZipProduct(name=entry["name"], url=entry["url"], currency="USD"),
            zip_code=response.meta["zip_code"],
            stores=stores,
            in_stock_count=in_stock,
        )
        item.url = entry["url"]
        yield item
