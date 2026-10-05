import os

from dotenv import load_dotenv

import ralphlauren.page_objects  # noqa: E402,F401  registers @handle_urls rules
import ralphlauren.session_configs  # noqa: E402,F401  registers @session_config rules

load_dotenv()

BOT_NAME = "ralphlauren"
SPIDER_MODULES = ["ralphlauren.spiders"]
NEWSPIDER_MODULE = "ralphlauren.spiders"

ROBOTSTXT_OBEY = True

ADDONS = {
    "scrapy_poet.Addon": 400,
    "scrapy_zyte_api.Addon": 500,
}

ZYTE_API_KEY = os.getenv("ZYTE_API_KEY")
ZIP_CODES = [z.strip() for z in os.getenv("ZIP_CODES", "10001,90210,60601").split(",") if z.strip()]
USER_AGENT = ""  # "" passes RobotsTxtMiddleware's check but sends no UA header → Zyte API sets one
ZYTE_API_SESSION_POOL_SIZE = 1  # one sticky session per zip pool = one shopper per zip
# Sessions are opted in per-request by ZipCodeCrawlMixin (zyte_api_session_enabled
# meta), NOT globally — otherwise even the robots.txt fetch pulls a browser session.

DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_CONCURRENCY = 1
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_MAX_CONCURRENCY = 4

DOWNLOADER_MIDDLEWARES = {
    "ralphlauren.middlewares.ZipStatsMiddleware": 550,
}

ITEM_PIPELINES = {
    "ralphlauren.pipelines.ProductValidationPipeline": 100,
    "ralphlauren.pipelines.DuplicateFilterPipeline": 200,
    "ralphlauren.pipelines.PerZipCodeExportPipeline": 300,
}

OUTPUT_DIR = "output"

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"
