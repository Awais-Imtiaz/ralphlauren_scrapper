from web_poet import HttpResponse, ItemPage, field, handle_urls
from zyte_common_items import Brand, Image

from ralphlauren.items import ZipProduct


@handle_urls("www.ralphlauren.com")
class ProductPage(ItemPage[ZipProduct]):
    """PDP extraction — selectors verified against live pages (docs/07).

    Ralph Lauren PDPs carry no Product JSON-LD (only Organization/WebSite/
    WebPage), so extraction is CSS over stable hooks: hidden price inputs,
    js-product-* classes and meta tags.
    """

    selectors = {
        "name": "h1.product-name::text",
        "price_range": "input.js-product-normal-prices::attr(value)",
        "pid": "input.js-product-rec-pid::attr(value)",
        "description": "meta[name='description']::attr(content)",
        "image": "meta[property='og:image']::attr(content)",
    }

    def __init__(self, response: HttpResponse):
        self.response = response

    @field
    def url(self) -> str:
        return str(self.response.url)

    @field
    def name(self):
        return (self.response.css(self.selectors["name"]).get() or "").strip() or None

    @field
    def price(self):
        hidden = self.response.css(self.selectors["price_range"]).get()
        if hidden and " - " in hidden:
            return hidden.split(" - ")[0].strip()
        return hidden or None

    @field
    def currency(self) -> str:
        return "USD"

    @field
    def sku(self):
        return self.response.css(self.selectors["pid"]).get()

    @field
    def description(self):
        return self.response.css(self.selectors["description"]).get()

    @field
    def brand(self):
        return Brand(name="Ralph Lauren")

    @field
    def images(self):
        if url := self.response.css(self.selectors["image"]).get():
            return [Image(url=url)]
        return None
