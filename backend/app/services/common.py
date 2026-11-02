import re
from datetime import timezone

from sqlalchemy import func, select

from app.errors import InventoryError
from app.models import Product, StockMovement

MAX_INT = 2_147_483_647


def integer(value, field, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_INT:
        raise InventoryError("INVALID_INPUT", f"Enter a whole number between {minimum:,} and {MAX_INT:,}.", field)
    return value


def clean_text(value, field, maximum, multiline=False):
    allowed = "\n\r\t" if multiline else ""
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum or any(ord(c) < 32 and c not in allowed for c in value):
        raise InventoryError("INVALID_INPUT", f"Enter 1–{maximum} characters without unsupported control characters.", field)
    return value.strip()


def clean_sku(value):
    value = clean_text(value, "sku", 64).upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/\-]{0,63}", value):
        raise InventoryError("INVALID_INPUT", "Start with a letter or number; use only letters, numbers, dots, slashes, hyphens, or underscores.", "sku")
    return value


def product_id(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    if not 1 <= parsed <= 9_223_372_036_854_775_807 or str(parsed) != str(value):
        raise InventoryError("INVALID_INPUT", "Invalid product ID.", "id")
    return parsed


def page_args(limit, offset):
    integer(limit, "limit", 1)
    integer(offset, "offset")
    if limit > 100:
        raise InventoryError("INVALID_INPUT", "Page size cannot exceed 100.", "limit")


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def product_statement():
    balances = select(StockMovement.product_id, func.sum(StockMovement.quantity_change).label("balance")).group_by(StockMovement.product_id).subquery()
    balance = func.coalesce(balances.c.balance, 0)
    return select(Product, balance.label("current_stock")).outerjoin(balances, Product.id == balances.c.product_id), balance


def product_data(product, balance):
    return {
        "id": str(product.id), "sku": product.sku, "name": product.name,
        "category": product.category, "unit_price_minor": product.unit_price_minor,
        "low_stock_threshold": product.low_stock_threshold, "current_stock": balance,
        "is_low_stock": balance <= product.low_stock_threshold,
        "created_at": aware(product.created_at), "updated_at": aware(product.updated_at),
        "archived_at": aware(product.archived_at),
    }


def find_product(session, id, active=False):
    product = session.get(Product, product_id(id))
    if product is None:
        raise InventoryError("PRODUCT_NOT_FOUND", "Product was not found.", "id")
    if active and product.archived_at:
        raise InventoryError("PRODUCT_ARCHIVED", "Archived products are read-only.", "id")
    return product


def balance_for(session, id):
    return session.scalar(select(func.coalesce(func.sum(StockMovement.quantity_change), 0)).where(StockMovement.product_id == id))


def movement_data(movement, product):
    return {
        "id": str(movement.id), "product_id": str(product.id), "product_sku": product.sku,
        "product_name": product.name, "movement_type": movement.movement_type,
        "quantity_change": movement.quantity_change, "reason": movement.reason,
        "created_at": aware(movement.created_at),
    }
