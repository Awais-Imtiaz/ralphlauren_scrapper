import attrs

from zyte_common_items import Product


@attrs.define
class ZipProduct(Product):
    """zyte-common-items Product plus zip-scoped store availability."""

    zip_code: str = attrs.field(default="")
    stores: list = attrs.field(factory=list)
    in_stock_count: int = attrs.field(default=0)
