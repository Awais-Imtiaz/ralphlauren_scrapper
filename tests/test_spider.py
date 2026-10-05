import unittest

from ralphlauren.spiders.products import ProductsSpider


class ZipResolutionTest(unittest.TestCase):
    def test_cli_overrides_everything(self):
        spider = ProductsSpider(zip_codes="10001,90210")
        self.assertEqual(spider.zip_codes, ["10001", "90210"])

    def test_single_cli_zip(self):
        self.assertEqual(ProductsSpider(zip_codes="33101").zip_codes, ["33101"])

    def test_invalid_zip_raises(self):
        with self.assertRaises(ValueError):
            ProductsSpider(zip_codes="1000")  # 4 digits

    def test_class_default_when_no_cli(self):
        spider = ProductsSpider()
        self.assertEqual(spider.zip_codes, ProductsSpider.zip_codes)


if __name__ == "__main__":
    unittest.main()
