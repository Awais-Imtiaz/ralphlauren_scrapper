from web_poet import handle_urls
from web_poet.pages import WebPage


@handle_urls("www.ralphlauren.com")
class ListingPage(WebPage):
    """Category listing navigation and tile extraction.

    Selectors verified against live pages: tiles expose product data as
    data-* attributes, prices render under .price, paging is a
    "View 30 more" button (a.more-button).
    """

    selectors = {
        "tile": ".product-tile",
        "link": "a.thumb-link::attr(href)",
        "price": ".price ::text",
        "next_page": "a.more-button::attr(href)",
    }

    def product_entries(self) -> list[dict]:
        entries = []
        for tile in self.css(self.selectors["tile"]):
            pid = (tile.xpath("@data-itemid").get() or "").removesuffix("-P")
            name = (tile.xpath("@data-pname").get() or "").strip()
            price = next(
                (t.strip().lstrip("$") for t in tile.css(self.selectors["price"]).getall() if t.strip()),
                None,
            )
            href = tile.css(self.selectors["link"]).get()
            if pid and name and href:
                entries.append(
                    {
                        "pid": pid,
                        "name": name,
                        "price": price,
                        "url": str(self.response.urljoin(href)),
                    }
                )
        return entries

    def next_page_url(self):
        next_url = self.css(self.selectors["next_page"]).get()
        return str(self.response.urljoin(next_url)) if next_url else None
