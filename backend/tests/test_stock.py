from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import Database
from app.errors import InventoryError
from app.services import products, stock


def test_receive_issue_adjust_ledger(database, make_product):
    product = make_product(opening_quantity=10)
    stock.change_stock(database, product["id"], "RECEIVED", 5, "Delivery")
    stock.change_stock(database, product["id"], "ISSUED", 3, "Shop use")
    result = stock.change_stock(database, product["id"], "ADJUSTMENT", 9, "Physical count")
    assert result["product"]["current_stock"] == 9
    assert result["movement"]["quantity_change"] == -3
    movements = stock.list_movements(database)["items"]
    assert [movement["quantity_change"] for movement in movements] == [-3, -3, 5, 10]
    assert sum(movement["quantity_change"] for movement in movements) == 9


@pytest.mark.parametrize("kind,quantity,reason,code", [
    ("ISSUED", 11, "Too many", "INSUFFICIENT_STOCK"),
    ("RECEIVED", 0, "None", "INVALID_INPUT"),
    ("ISSUED", -1, "Negative", "INVALID_INPUT"),
    ("ADJUSTMENT", 9, "   ", "INVALID_INPUT"),
    ("ADJUSTMENT", -1, "Negative", "INVALID_INPUT"),
    ("ADJUSTMENT", 10, "No change", "NO_CHANGE"),
    ("RECEIVED", 2_147_483_647, "Overflow", "INVALID_INPUT"),
])
def test_failed_movements_leave_no_changes(database, make_product, kind, quantity, reason, code):
    product = make_product()
    with pytest.raises(InventoryError) as error:
        stock.change_stock(database, product["id"], kind, quantity, reason)
    assert error.value.code == code
    assert products.get_product(database, product["id"])["current_stock"] == 10
    assert stock.list_movements(database)["total_count"] == 1


def test_concurrent_issues_are_serialized_across_connections(database, make_product):
    product = make_product(opening_quantity=10)
    other_database = Database(database.path)
    barrier = Barrier(2)

    def issue(db):
        barrier.wait(timeout=10)
        try:
            stock.change_stock(db, product["id"], "ISSUED", 7, "Concurrent issue")
            return "OK"
        except InventoryError as error:
            return error.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(issue, db) for db in (database, other_database)]
            outcomes = [future.result(timeout=20) for future in futures]
        assert sorted(outcomes) == ["INSUFFICIENT_STOCK", "OK"]
        assert products.get_product(database, product["id"])["current_stock"] == 3
        assert stock.list_movements(database)["total_count"] == 2
    finally:
        other_database.dispose()


def test_concurrent_receipts_do_not_lose_updates(database, make_product):
    product = make_product(opening_quantity=0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(stock.change_stock, database, product["id"], "RECEIVED", 1, "Delivery") for _ in range(12)]
        for future in futures:
            future.result(timeout=20)
    assert products.get_product(database, product["id"])["current_stock"] == 12
    assert stock.list_movements(database)["total_count"] == 13


def test_product_and_opening_movement_are_atomic(database, make_product):
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TRIGGER reject_opening BEFORE INSERT ON stock_movements BEGIN SELECT RAISE(ABORT, 'test rejection'); END")
    with pytest.raises(InventoryError):
        make_product()
    assert products.list_products(database)["total_count"] == 0


def test_failed_insert_rolls_back_product_timestamp(database, make_product):
    product = make_product()
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TRIGGER reject_received BEFORE INSERT ON stock_movements WHEN NEW.movement_type = 'RECEIVED' BEGIN SELECT RAISE(ABORT, 'test rejection'); END")
    with pytest.raises(InventoryError):
        stock.change_stock(database, product["id"], "RECEIVED", 1, "Delivery")
    after = products.get_product(database, product["id"])
    assert after["updated_at"] == product["updated_at"]
    assert after["current_stock"] == 10
    assert stock.list_movements(database)["total_count"] == 1


def test_ledger_is_immutable_at_database_level(database, make_product):
    make_product()
    with pytest.raises(IntegrityError):
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE stock_movements SET quantity_change = 1"))
    with pytest.raises(IntegrityError):
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM stock_movements"))


def test_history_filters_and_invalid_dates(database, make_product):
    product = make_product()
    stock.change_stock(database, product["id"], "RECEIVED", 2, "Delivery")
    today = date.today()
    result = stock.list_movements(database, {"movement_type": "RECEIVED", "search": "NOTE", "from_date": today - timedelta(days=1), "to_date": today + timedelta(days=1)})
    assert result["total_count"] == 1
    with pytest.raises(InventoryError):
        stock.list_movements(database, {"from_date": today, "to_date": today - timedelta(days=1)})


def test_database_busy_is_a_useful_error_and_does_not_write(database, make_product):
    product = make_product()
    competing = Database(database.path)
    try:
        with competing.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA busy_timeout=20")
        with database.write():
            with pytest.raises(InventoryError) as error:
                stock.change_stock(competing, product["id"], "ISSUED", 1, "Competing issue")
        assert error.value.code == "DATABASE_BUSY"
        assert products.get_product(database, product["id"])["current_stock"] == 10
    finally:
        competing.dispose()


def test_adjustment_supports_multiline_reason(database, make_product):
    product = make_product()
    result = stock.change_stock(database, product["id"], "ADJUSTMENT", 9, "Physical count\nOne damaged item removed")
    assert result["movement"]["reason"] == "Physical count\nOne damaged item removed"


def test_concurrent_archive_and_receipt_cannot_hide_nonzero_stock(database, make_product):
    product = make_product(opening_quantity=0)
    barrier = Barrier(2)

    def attempt(operation):
        barrier.wait(timeout=10)
        try:
            if operation == "archive":
                products.archive_product(database, product["id"])
            else:
                stock.change_stock(database, product["id"], "RECEIVED", 1, "Concurrent delivery")
            return operation, "OK"
        except InventoryError as error:
            return operation, error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, operation) for operation in ("archive", "receive")]
        outcomes = dict(future.result(timeout=20) for future in futures)
    after = products.get_product(database, product["id"])
    if after["archived_at"]:
        assert outcomes == {"archive": "OK", "receive": "PRODUCT_ARCHIVED"}
        assert after["current_stock"] == 0
        assert stock.list_movements(database)["total_count"] == 1
    else:
        assert outcomes == {"archive": "NONZERO_STOCK", "receive": "OK"}
        assert after["current_stock"] == 1
        assert stock.list_movements(database)["total_count"] == 2
