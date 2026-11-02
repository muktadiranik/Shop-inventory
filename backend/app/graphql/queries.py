import strawberry
from strawberry.types import Info

from app.graphql.calls import query_call
from app.graphql.inputs import MovementFilter, ProductFilter
from app.graphql.types import (
    ArchiveStatus, CsvExport, DashboardSummary, MovementPage, Product,
    ProductPage, as_movement, as_product,
)
from app.services import products, reporting, stock


@strawberry.type
class Query:
    @strawberry.field
    async def dashboard(self, info: Info) -> DashboardSummary:
        return DashboardSummary(**await query_call(info, reporting.dashboard))

    @strawberry.field
    async def products(self, info: Info, filter: ProductFilter | None = None, limit: int = 20, offset: int = 0) -> ProductPage:
        data = await query_call(info, products.list_products, filter.as_dict() if filter else None, limit, offset)
        return ProductPage(items=[as_product(item) for item in data["items"]], total_count=data["total_count"])

    @strawberry.field
    async def product(self, info: Info, id: strawberry.ID) -> Product | None:
        return as_product(await query_call(info, products.get_product, id))

    @strawberry.field
    async def categories(self, info: Info, archive_status: ArchiveStatus = ArchiveStatus.ACTIVE) -> list[str]:
        return await query_call(info, products.categories, archive_status.value)

    @strawberry.field
    async def stock_movements(self, info: Info, filter: MovementFilter | None = None, limit: int = 20, offset: int = 0) -> MovementPage:
        data = await query_call(info, stock.list_movements, filter.as_dict() if filter else None, limit, offset)
        return MovementPage(items=[as_movement(item) for item in data["items"]], total_count=data["total_count"])

    @strawberry.field
    async def inventory_csv(self, info: Info, filter: ProductFilter | None = None) -> CsvExport:
        return CsvExport(**await query_call(info, reporting.inventory_csv, filter.as_dict() if filter else None))
