import csv
import io

import pytest

from app.errors import InventoryError
from app.services import products, reporting, stock


def test_opening_stock_and_normalization(database, make_product):
    product = make_product(sku="  book-01  ", opening_quantity=0)
    assert product["sku"] == "BOOK-01"
    assert product["current_stock"] == 0
    assert product["is_low_stock"]
    movements = stock.list_movements(database, {"product_id": product["id"]})
    assert movements["total_count"] == 1
    assert movements["items"][0]["movement_type"] == "OPENING"
    assert movements["items"][0]["quantity_change"] == 0
    assert movements["items"][0]["created_at"].tzinfo is not None


def test_duplicate_sku_including_archive(database, make_product):
    product = make_product(sku="unique", opening_quantity=0)
    products.archive_product(database, product["id"])
    with pytest.raises(InventoryError) as error:
        make_product(sku="UNIQUE")
    assert error.value.code == "DUPLICATE_SKU"
    assert products.list_products(database, {"archive_status": "ALL"})["total_count"] == 1


@pytest.mark.parametrize("values,field", [
    ({"name": "   "}, "name"), ({"category": ""}, "category"),
    ({"unit_price_minor": -1}, "unitPriceMinor"), ({"unit_price_minor": 1.25}, "unitPriceMinor"),
    ({"low_stock_threshold": -1}, "lowStockThreshold"), ({"opening_quantity": -1}, "openingQuantity"),
    ({"sku": "bad sku"}, "sku"), ({"name": "bad\nname"}, "name"),
])
def test_product_validation(database, make_product, values, field):
    with pytest.raises(InventoryError) as error:
        make_product(**values)
    assert error.value.field == field
    assert products.list_products(database)["total_count"] == 0


def test_filters_pagination_and_literal_search(database, make_product):
    make_product(name="A pen", category="Office", opening_quantity=3)
    make_product(name="B pencil", category="office", opening_quantity=8)
    make_product(name="100% cotton", category="Clothing", opening_quantity=0)
    assert products.categories(database) == ["Clothing", "Office"]
    assert products.list_products(database, {"search": "PEN", "category": "office"})["total_count"] == 2
    assert products.list_products(database, {"search": "%"})["total_count"] == 1
    assert products.list_products(database, {"low_stock_only": True})["total_count"] == 2
    page = products.list_products(database, limit=1, offset=1)
    assert len(page["items"]) == 1
    assert page["total_count"] == 3


def test_edit_metadata_does_not_change_stock_or_history(database, make_product):
    product = make_product(unit_price_minor=29)
    result = products.update_product(database, product["id"], {"name": "New name", "category": "Other", "unit_price_minor": 101, "low_stock_threshold": 11})
    assert result["product"]["sku"] == product["sku"]
    assert result["product"]["unit_price_minor"] == 101
    assert result["product"]["current_stock"] == 10
    assert result["product"]["is_low_stock"]
    assert stock.list_movements(database)["total_count"] == 1


def test_archive_preserves_history_and_dashboard(database, make_product):
    active = make_product(name="Active", opening_quantity=5)
    archived = make_product(name="Archived", opening_quantity=2)
    with pytest.raises(InventoryError, match="zero"):
        products.archive_product(database, archived["id"])
    stock.change_stock(database, archived["id"], "ISSUED", 2, "Final units issued")
    products.archive_product(database, archived["id"])
    assert products.get_product(database, archived["id"])["archived_at"]
    assert stock.list_movements(database, {"product_id": archived["id"]})["total_count"] == 2
    assert products.list_products(database)["total_count"] == 1
    assert products.list_products(database, {"archive_status": "ARCHIVED"})["items"][0]["id"] == archived["id"]
    assert reporting.dashboard(database) == {"product_count": 1, "total_units": "5", "low_stock_count": 0}
    with pytest.raises(InventoryError) as error:
        stock.change_stock(database, archived["id"], "RECEIVED", 1, "Not allowed")
    assert error.value.code == "PRODUCT_ARCHIVED"
    with pytest.raises(InventoryError):
        products.update_product(database, archived["id"], {"name": "Changed", "category": "X", "unit_price_minor": 1, "low_stock_threshold": 0})


def test_csv_all_matching_rows_money_escaping_and_formula_safety(database, make_product):
    make_product(name='=HYPERLINK("bad")', category="A, B", unit_price_minor=29)
    make_product(name='A "quoted" item', category="Other", unit_price_minor=101)
    exported = reporting.inventory_csv(database)
    rows = list(csv.reader(io.StringIO(exported["content"])))
    assert len(rows) == 3
    assert any(row[1].startswith("'=") and row[3] == "0.29" and row[2] == "A, B" for row in rows[1:])
    assert len(list(csv.reader(io.StringIO(reporting.inventory_csv(database, {"category": "Other"})["content"])))) == 2


def test_empty_dashboard(database):
    assert reporting.dashboard(database) == {"product_count": 0, "total_units": "0", "low_stock_count": 0}


def test_aggregate_total_does_not_overflow_graphql_int(database, make_product):
    make_product(opening_quantity=2_147_483_647)
    make_product(opening_quantity=2_147_483_647)
    assert reporting.dashboard(database)["total_units"] == "4294967294"
