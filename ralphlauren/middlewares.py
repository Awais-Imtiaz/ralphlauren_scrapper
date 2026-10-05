from scrapy_zyte_api import is_session_init_request


class ZipStatsMiddleware:
    """Downloader middleware: per-zip response counters and error logging."""

    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response):
        zip_code = request.meta.get("zip_code")
        if zip_code:
            self.crawler.stats.inc_value(f"zip/{zip_code}/responses")
        if response.status >= 400:
            self.crawler.logger.warning(
                "HTTP %s in zip %s: %s", response.status, zip_code, request.url
            )
        return response

    def process_exception(self, request, exception):
        # Session-init failures are swallowed silently by scrapy-zyte-api's
        # session manager (except Exception -> False, 8x -> TooManyBadSessionInits
        # with no explanation) — this hook still sees them, so log the cause.
        zip_code = request.meta.get("zip_code")
        if zip_code:
            self.crawler.stats.inc_value(f"zip/{zip_code}/errors")
        self.crawler.logger.warning(
            "download failed (zip=%s, init=%s): %s: %s — %s",
            zip_code or "?",
            is_session_init_request(request),
            type(exception).__name__,
            exception,
            request.url,
        )
        return None
