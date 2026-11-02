from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price_minor BETWEEN 0 AND 2147483647", name="ck_product_price"),
        CheckConstraint("low_stock_threshold BETWEEN 0 AND 2147483647", name="ck_product_threshold"),
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 160", name="ck_product_name"),
        CheckConstraint("length(trim(category)) BETWEEN 1 AND 80", name="ck_product_category"),
        CheckConstraint("length(sku) BETWEEN 1 AND 64 AND sku = upper(sku)", name="ck_product_sku"),
        Index("ix_products_category", "category"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    low_stock_threshold: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "(movement_type = 'OPENING' AND quantity_change >= 0) OR "
            "(movement_type = 'RECEIVED' AND quantity_change > 0) OR "
            "(movement_type = 'ISSUED' AND quantity_change < 0) OR "
            "(movement_type = 'ADJUSTMENT' AND quantity_change != 0)",
            name="ck_movement_sign",
        ),
        CheckConstraint("quantity_change BETWEEN -2147483647 AND 2147483647", name="ck_movement_quantity"),
        CheckConstraint("length(trim(reason)) BETWEEN 1 AND 500", name="ck_movement_reason"),
        Index("ix_movements_product_created", "product_id", "created_at", "id"),
        Index("ix_movements_created", "created_at", "id"),
        Index("uq_movement_opening", "product_id", unique=True, sqlite_where=text("movement_type = 'OPENING'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    movement_type: Mapped[str] = mapped_column(String(16))
    quantity_change: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
