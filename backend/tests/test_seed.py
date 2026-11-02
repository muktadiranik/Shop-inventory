from datetime import datetime, timezone
import sqlite3

import pytest
from sqlalchemy import func, select

from app.errors import InventoryError
from app.models import Product, StockMovement
from app.seed import backup_database, build_seed, seed_database
from app.services import products, reporting, stock
from app.services.common import aware

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


def test_seed_has_realistic_related_history_and_stock_states(database):
    result = seed_database(database, NOW)
    assert result == {"created_products": 120, "created_movements": 760, "skipped_existing_products": 0}
    assert len(products.categories(database, "ALL")) == 12
    assert products.list_products(database)["total_count"] == 114
    assert products.list_products(database, {"archive_status": "ARCHIVED"})["total_count"] == 6
    assert reporting.dashboard(database)["low_stock_count"] == 31
    kinds = set()
    with database.read() as session:
        for product in session.scalars(select(Product)):
            movements = list(session.scalars(select(StockMovement).where(StockMovement.product_id == product.id).order_by(StockMovement.created_at, StockMovement.id)))
            assert movements[0].movement_type == "OPENING"
            assert sum(row.movement_type == "OPENING" for row in movements) == 1
            balance = 0
            for row in movements:
                balance += row.quantity_change
                assert balance >= 0
                assert aware(product.created_at) <= aware(row.created_at) <= NOW
                assert row.reason.strip()
                kinds.add(row.movement_type)
            if product.archived_at:
                assert balance == 0
                assert aware(product.archived_at) >= aware(movements[-1].created_at)
            assert product.unit_price_minor > 0
            assert isinstance(product.unit_price_minor, int)
            if product.category == "Dairy & Chilled":
                assert (NOW - aware(product.created_at)).days <= 7
    assert kinds == {"OPENING", "RECEIVED", "ISSUED", "ADJUSTMENT"}


def test_repeat_seed_does_not_duplicate_or_overwrite_operator_changes(database):
    seed_database(database, NOW)
    product = products.list_products(database, {"search": "GRA-001"})["items"][0]
    stock.change_stock(database, product["id"], "RECEIVED", 3, "Actual shop delivery")
    products.update_product(database, product["id"], {"name": "Operator's rice label", "category": product["category"], "unit_price_minor": 321, "low_stock_threshold": 2})
    before = products.get_product(database, product["id"])
    history = stock.list_movements(database, {"product_id": product["id"]})
    assert seed_database(database, NOW) == {"created_products": 0, "created_movements": 0, "skipped_existing_products": 120}
    assert products.get_product(database, product["id"]) == before
    assert stock.list_movements(database, {"product_id": product["id"]}) == history
    with database.read() as session:
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 761


def test_existing_sku_and_history_are_preserved(database, make_product):
    existing = make_product(sku="GRA-001", name="Existing shop item", opening_quantity=7)
    before = stock.list_movements(database, {"product_id": existing["id"]})
    result = seed_database(database, NOW)
    assert result["created_products"] == 119
    assert result["skipped_existing_products"] == 1
    assert products.get_product(database, existing["id"]) == existing
    assert stock.list_movements(database, {"product_id": existing["id"]}) == before


def test_seed_failure_rolls_back_entire_batch(database, make_product):
    existing = make_product(sku="USER-ITEM")
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TRIGGER reject_seed BEFORE INSERT ON stock_movements WHEN (SELECT sku FROM products WHERE id = NEW.product_id) = 'BEV-005' BEGIN SELECT RAISE(ABORT, 'Injected seed failure'); END")
    with pytest.raises(InventoryError):
        seed_database(database, NOW)
    assert products.list_products(database, {"archive_status": "ALL"})["total_count"] == 1
    assert products.get_product(database, existing["id"]) == existing
    assert stock.list_movements(database)["total_count"] == 1


def test_backup_is_a_consistent_pre_seed_snapshot(database, make_product):
    make_product()
    path = backup_database(database)
    seed_database(database, NOW)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT count(*) FROM products").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM stock_movements").fetchone()[0] == 1


def test_seed_plan_is_deterministic_and_rejects_naive_timestamps():
    assert build_seed(NOW) == build_seed(NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_seed(datetime(2026, 11, 2))
