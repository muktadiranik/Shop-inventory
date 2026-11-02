from datetime import date

import strawberry

from app.graphql.types import ArchiveStatus, MovementType


@strawberry.input
class ProductFilter:
    search: str | None = None
    category: str | None = None
    low_stock_only: bool = False
    archive_status: ArchiveStatus = ArchiveStatus.ACTIVE

    def as_dict(self):
        return {"search": self.search, "category": self.category, "low_stock_only": self.low_stock_only, "archive_status": self.archive_status.value}


@strawberry.input
class MovementFilter:
    search: str | None = None
    product_id: strawberry.ID | None = None
    movement_type: MovementType | None = None
    from_date: date | None = None
    to_date: date | None = None

    def as_dict(self):
        return {"search": self.search, "product_id": self.product_id, "movement_type": self.movement_type.value if self.movement_type else None, "from_date": self.from_date, "to_date": self.to_date}


@strawberry.input
class CreateProductInput:
    sku: str
    name: str
    category: str
    unit_price_minor: int
    low_stock_threshold: int
    opening_quantity: int


@strawberry.input
class UpdateProductInput:
    id: strawberry.ID
    name: str
    category: str
    unit_price_minor: int
    low_stock_threshold: int


@strawberry.input
class StockInput:
    product_id: strawberry.ID
    quantity: int
    reason: str


@strawberry.input
class AdjustmentInput:
    product_id: strawberry.ID
    counted_quantity: int
    reason: str
