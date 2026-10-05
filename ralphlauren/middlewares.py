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
        zip_code = request.meta.get("zip_code")
        if zip_code:
            self.crawler.stats.inc_value(f"zip/{zip_code}/errors")
        return None
