import asyncio
import unittest
from pathlib import Path

from web_poet import HttpResponse

from ralphlauren.page_objects.listing_page import ListingPage
from ralphlauren.page_objects.product_page import ProductPage

FIXTURES = Path(__file__).parent / "fixtures"


class ProductPageTest(unittest.TestCase):
    def test_extraction_from_live_fixture(self):
        html = (FIXTURES / "pdp_fragment.html").read_text()
        page = ProductPage(
            response=HttpResponse(
                "https://www.ralphlauren.com/men-clothing-polo-shirts/x/401480-P.html",
                body=html.encode(),
            )
        )
        item = asyncio.run(page.to_item())
        self.assertEqual(item.name, "The Iconic Mesh Polo Shirt - All Fits")
        self.assertEqual(item.price, "74.99")  # low end of "74.99 - 118.0"
        self.assertEqual(item.sku, "401480")
        self.assertEqual(item.currency, "USD")
        self.assertEqual(item.brand.name, "Ralph Lauren")
        self.assertTrue(item.description)
        self.assertTrue(item.images[0].url.startswith("https://"))


class ListingPageTest(unittest.TestCase):
    def test_entries_and_pagination_from_live_fixture(self):
        html = (FIXTURES / "listing_tile.html").read_text()
        listing = ListingPage(
            response=HttpResponse("https://www.ralphlauren.com/men-clothing", html.encode())
        )
        entries = listing.product_entries()
        self.assertTrue(entries)
        first = entries[0]
        self.assertEqual(first["pid"], "401480")  # "-P" suffix stripped
        self.assertEqual(first["name"], "The Iconic Mesh Polo Shirt - All Fits")
        self.assertEqual(first["price"], "74.99")
        self.assertTrue(first["url"].startswith("https://www.ralphlauren.com/"))
        self.assertEqual(
            listing.next_page_url(),
            "https://www.ralphlauren.com/men-clothing?page=2",
        )


class _FakeResponse:
    """Minimal response shell so ItemPage can use .css/.urljoin."""

    def __init__(self, url, html):
        from scrapy.http import HtmlResponse

        self._r = HtmlResponse(url, body=html, encoding="utf-8")
        self.url = url

    def css(self, *a, **kw):
        return self._r.css(*a, **kw)

    def urljoin(self, *a, **kw):
        return self._r.urljoin(*a, **kw)


if __name__ == "__main__":
    unittest.main()
