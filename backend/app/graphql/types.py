from datetime import datetime
from enum import Enum

import strawberry


@strawberry.enum
class ArchiveStatus(Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ALL = "ALL"


@strawberry.enum
class MovementType(Enum):
    OPENING = "OPENING"
    RECEIVED = "RECEIVED"
    ISSUED = "ISSUED"
    ADJUSTMENT = "ADJUSTMENT"


@strawberry.type
class Product:
    id: strawberry.ID
    sku: str
    name: str
    category: str
    unit_price_minor: int
    low_stock_threshold: int
    current_stock: int
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


@strawberry.type
class StockMovement:
    id: strawberry.ID
    product_id: strawberry.ID
    product_sku: str
    product_name: str
    movement_type: MovementType
    quantity_change: int
    reason: str
    created_at: datetime


@strawberry.type
class ProductPage:
    items: list[Product]
    total_count: int


@strawberry.type
class MovementPage:
    items: list[StockMovement]
    total_count: int


@strawberry.type
class DashboardSummary:
    product_count: int
    total_units: str = strawberry.field(description="Nonnegative decimal digit string; avoids GraphQL Int overflow on aggregate totals.")
    low_stock_count: int


@strawberry.type
class CsvExport:
    filename: str
    content_type: str
    content: str


@strawberry.type
class UserError:
    code: str
    message: str
    field: str | None


@strawberry.type
class MutationResult:
    product: Product | None = None
    movement: StockMovement | None = None
    errors: list[UserError] = strawberry.field(default_factory=list)


def as_product(data):
    return Product(**data) if data else None


def as_movement(data):
    return StockMovement(**{**data, "movement_type": MovementType(data["movement_type"])}) if data else None
