from sqlalchemy import func, select

from app.errors import InventoryError
from app.models import Product, StockMovement, utcnow
from app.services.common import (
    balance_for, clean_sku, clean_text, find_product, integer,
    movement_data, page_args, product_data, product_id, product_statement,
)


def filtered_statement(filters=None):
    filters = filters or {}
    statement, balance = product_statement()
    status = filters.get("archive_status", "ACTIVE")
    if status == "ACTIVE":
        statement = statement.where(Product.archived_at.is_(None))
    elif status == "ARCHIVED":
        statement = statement.where(Product.archived_at.is_not(None))
    elif status != "ALL":
        raise InventoryError("INVALID_INPUT", "Invalid archive status.", "archiveStatus")
    search = (filters.get("search") or "").strip()
    if len(search) > 160:
        raise InventoryError("INVALID_INPUT", "Search cannot exceed 160 characters.", "search")
    if search:
        statement = statement.where(Product.sku.icontains(search, autoescape=True) | Product.name.icontains(search, autoescape=True))
    if filters.get("category"):
        statement = statement.where(func.lower(Product.category) == filters["category"].strip().lower())
    if filters.get("low_stock_only"):
        statement = statement.where(balance <= Product.low_stock_threshold)
    return statement


def list_products(database, filters=None, limit=20, offset=0):
    page_args(limit, offset)
    statement = filtered_statement(filters)
    with database.read() as session:
        count = session.scalar(select(func.count()).select_from(statement.subquery()))
        rows = session.execute(statement.order_by(func.lower(Product.name), Product.id).limit(limit).offset(offset)).all()
        return {"items": [product_data(product, balance) for product, balance in rows], "total_count": count}


def get_product(database, id):
    id = product_id(id)
    statement, _ = product_statement()
    with database.read() as session:
        row = session.execute(statement.where(Product.id == id)).first()
        return product_data(*row) if row else None


def categories(database, archive_status="ACTIVE"):
    statement = select(Product.category).distinct()
    if archive_status == "ACTIVE":
        statement = statement.where(Product.archived_at.is_(None))
    elif archive_status == "ARCHIVED":
        statement = statement.where(Product.archived_at.is_not(None))
    with database.read() as session:
        return list(session.scalars(statement.order_by(func.lower(Product.category))))


def validated_fields(values):
    return {
        "name": clean_text(values["name"], "name", 160),
        "category": clean_text(values["category"], "category", 80),
        "unit_price_minor": integer(values["unit_price_minor"], "unitPriceMinor"),
        "low_stock_threshold": integer(values["low_stock_threshold"], "lowStockThreshold"),
    }


def canonical_category(session, category):
    return session.scalar(select(Product.category).where(func.lower(Product.category) == category.lower()).limit(1)) or category


def create_product(database, values):
    fields = validated_fields(values)
    sku = clean_sku(values["sku"])
    opening = integer(values["opening_quantity"], "openingQuantity")
    with database.write() as session:
        fields["category"] = canonical_category(session, fields["category"])
        product = Product(sku=sku, **fields)
        session.add(product)
        session.flush()
        movement = StockMovement(product_id=product.id, movement_type="OPENING", quantity_change=opening, reason="Opening stock")
        session.add(movement)
        session.flush()
        result = {"product": product_data(product, opening), "movement": movement_data(movement, product)}
    return result


def update_product(database, id, values):
    fields = validated_fields(values)
    with database.write() as session:
        product = find_product(session, id, active=True)
        fields["category"] = canonical_category(session, fields["category"])
        for field, value in fields.items():
            setattr(product, field, value)
        product.updated_at = utcnow()
        result = {"product": product_data(product, balance_for(session, product.id))}
    return result


def archive_product(database, id):
    with database.write() as session:
        product = find_product(session, id, active=True)
        if balance_for(session, product.id) != 0:
            raise InventoryError("NONZERO_STOCK", "Issue or adjust remaining stock to zero before archiving.", "id")
        product.archived_at = product.updated_at = utcnow()
        result = {"product": product_data(product, 0)}
    return result
