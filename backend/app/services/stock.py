from datetime import datetime, timezone

from sqlalchemy import func, select

from app.errors import InventoryError
from app.models import Product, StockMovement, utcnow
from app.services.common import (
    MAX_INT, balance_for, clean_text, find_product, integer, movement_data,
    page_args, product_data, product_id,
)


def change_stock(database, id, movement_type, quantity, reason):
    reason = clean_text(reason, "reason", 500, multiline=True)
    if movement_type not in {"RECEIVED", "ISSUED", "ADJUSTMENT"}:
        raise InventoryError("INVALID_INPUT", "Invalid stock operation.")
    field = "countedQuantity" if movement_type == "ADJUSTMENT" else "quantity"
    integer(quantity, field, 0 if movement_type == "ADJUSTMENT" else 1)
    with database.write() as session:
        product = find_product(session, id, active=True)
        current = balance_for(session, product.id)
        delta = quantity - current if movement_type == "ADJUSTMENT" else quantity * (-1 if movement_type == "ISSUED" else 1)
        new_balance = current + delta
        if new_balance < 0:
            raise InventoryError("INSUFFICIENT_STOCK", f"Only {current:,} units are available.", "quantity")
        if new_balance > MAX_INT:
            raise InventoryError("INVALID_INPUT", "The resulting stock exceeds the supported quantity.", field)
        if delta == 0:
            raise InventoryError("NO_CHANGE", "The counted quantity already matches the current stock.", field)
        movement = StockMovement(product_id=product.id, movement_type=movement_type, quantity_change=delta, reason=reason)
        session.add(movement)
        product.updated_at = utcnow()
        session.flush()
        result = {"product": product_data(product, new_balance), "movement": movement_data(movement, product)}
    return result


def list_movements(database, filters=None, limit=20, offset=0):
    page_args(limit, offset)
    filters = filters or {}
    statement = select(StockMovement, Product).join(Product)
    search = (filters.get("search") or "").strip()
    if len(search) > 160:
        raise InventoryError("INVALID_INPUT", "Search cannot exceed 160 characters.", "search")
    if search:
        statement = statement.where(Product.sku.icontains(search, autoescape=True) | Product.name.icontains(search, autoescape=True))
    if filters.get("product_id"):
        statement = statement.where(Product.id == product_id(filters["product_id"]))
    if filters.get("movement_type"):
        statement = statement.where(StockMovement.movement_type == filters["movement_type"])
    start, end = filters.get("from_date"), filters.get("to_date")
    if start and end and start > end:
        raise InventoryError("INVALID_INPUT", "Start date must not be after end date.", "fromDate")
    if start:
        statement = statement.where(StockMovement.created_at >= datetime.combine(start, datetime.min.time(), timezone.utc))
    if end:
        statement = statement.where(StockMovement.created_at <= datetime.combine(end, datetime.max.time(), timezone.utc))
    with database.read() as session:
        count = session.scalar(select(func.count()).select_from(statement.subquery()))
        rows = session.execute(statement.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(limit).offset(offset)).all()
        return {"items": [movement_data(movement, product) for movement, product in rows], "total_count": count}
