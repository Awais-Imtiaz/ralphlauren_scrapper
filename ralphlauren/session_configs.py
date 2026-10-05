from scrapy_zyte_api import SessionConfig, session_config


@session_config(["www.ralphlauren.com"])
class RalphLaurenSessionConfig(SessionConfig):
    """Per-zip session pools without setLocation.

    Zyte API's setLocation action is not supported on ralphlauren.com (the
    first live run closed with finish_reason=unsupported_set_location), so
    sessions warm up with a plain browserHtml request instead. Zip scoping
    still works: request meta (zyte_api_session_location) keeps one pool per
    zip, and zip-varying data comes from the StoreInventory endpoint queried
    inside each zip's session (see the spider).
    """

    def params(self, request):
        return {"browserHtml": True}

    def check(self, response, request):
        return True
