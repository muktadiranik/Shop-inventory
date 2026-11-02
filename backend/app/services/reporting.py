import csv
import io
from datetime import datetime, timezone

from sqlalchemy import Integer, func, select

from app.models import Product
from app.services.common import product_data, product_statement
from app.services.products import filtered_statement


def dashboard(database):
    statement, _ = product_statement()
    active = statement.where(Product.archived_at.is_(None)).subquery()
    with database.read() as session:
        row = session.execute(select(
            func.count().label("product_count"),
            func.coalesce(func.sum(active.c.current_stock), 0).label("total_units"),
            func.coalesce(func.sum((active.c.current_stock <= active.c.low_stock_threshold).cast(Integer)), 0).label("low_stock_count"),
        ).select_from(active)).one()
        # Total is a decimal digit string, so sums cannot overflow GraphQL's 32-bit Int.
        return {"product_count": row.product_count, "total_units": str(row.total_units), "low_stock_count": row.low_stock_count}


def safe_csv_text(value):
    # Quoting alone does not stop spreadsheet formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def inventory_csv(database, filters=None):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["SKU", "Name", "Category", "Unit price", "Current stock", "Low-stock threshold", "Low stock", "Archived"])
    with database.read() as session:
        rows = session.execute(filtered_statement(filters).order_by(func.lower(Product.name), Product.id))
        for product, balance in rows:
            data = product_data(product, balance)
            writer.writerow([
                safe_csv_text(product.sku), safe_csv_text(product.name), safe_csv_text(product.category),
                f"{product.unit_price_minor // 100}.{product.unit_price_minor % 100:02d}", balance,
                product.low_stock_threshold, "Yes" if data["is_low_stock"] else "No", "Yes" if product.archived_at else "No",
            ])
    return {"filename": f"inventory-{datetime.now(timezone.utc):%Y-%m-%d}.csv", "content_type": "text/csv;charset=utf-8", "content": output.getvalue()}
