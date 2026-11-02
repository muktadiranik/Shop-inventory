from dataclasses import asdict

import strawberry
from strawberry.types import Info

from app.errors import InventoryError
from app.graphql.calls import call
from app.graphql.inputs import AdjustmentInput, CreateProductInput, StockInput, UpdateProductInput
from app.graphql.types import MutationResult, UserError, as_movement, as_product
from app.services import products, stock


async def mutate(info, function, *args):
    try:
        result = await call(info, function, *args)
        return MutationResult(product=as_product(result.get("product")), movement=as_movement(result.get("movement")))
    except InventoryError as exc:
        return MutationResult(errors=[UserError(code=exc.code, message=exc.message, field=exc.field)])


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_product(self, info: Info, input: CreateProductInput) -> MutationResult:
        return await mutate(info, products.create_product, asdict(input))

    @strawberry.mutation
    async def update_product(self, info: Info, input: UpdateProductInput) -> MutationResult:
        values = asdict(input)
        id = values.pop("id")
        return await mutate(info, products.update_product, id, values)

    @strawberry.mutation
    async def receive_stock(self, info: Info, input: StockInput) -> MutationResult:
        return await mutate(info, stock.change_stock, input.product_id, "RECEIVED", input.quantity, input.reason)

    @strawberry.mutation
    async def issue_stock(self, info: Info, input: StockInput) -> MutationResult:
        return await mutate(info, stock.change_stock, input.product_id, "ISSUED", input.quantity, input.reason)

    @strawberry.mutation
    async def adjust_stock(self, info: Info, input: AdjustmentInput) -> MutationResult:
        return await mutate(info, stock.change_stock, input.product_id, "ADJUSTMENT", input.counted_quantity, input.reason)

    @strawberry.mutation
    async def archive_product(self, info: Info, id: strawberry.ID) -> MutationResult:
        return await mutate(info, products.archive_product, id)
