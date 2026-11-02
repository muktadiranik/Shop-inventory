"""HTTP/GraphQL contract tests against real migrated, temporary SQLite databases."""
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import io
from threading import Barrier

import pytest
from sqlalchemy import text

from app.models import StockMovement

PRODUCT = "id sku name category unitPriceMinor lowStockThreshold currentStock isLowStock createdAt updatedAt archivedAt"
MOVEMENT = "id productId productSku productName movementType quantityChange reason createdAt"
RESULT = f"product {{ {PRODUCT} }} movement {{ {MOVEMENT} }} errors {{ code field message }}"
CREATE = f"mutation Create($input: CreateProductInput!) {{ createProduct(input: $input) {{ {RESULT} }} }}"
UPDATE = f"mutation Update($input: UpdateProductInput!) {{ updateProduct(input: $input) {{ {RESULT} }} }}"
ARCHIVE = f"mutation Archive($id: ID!) {{ archiveProduct(id: $id) {{ {RESULT} }} }}"
SNAPSHOT = f"""query Snapshot($id: ID!) {{
  product(id: $id) {{ {PRODUCT} }}
  stockMovements(filter: {{productId: $id}}, limit: 100) {{ totalCount items {{ {MOVEMENT} }} }}
  dashboard {{ productCount totalUnits lowStockCount }}
}}"""


def request(client, query, variables=None):
    response = client.post("/graphql", json={"query": query, "variables": variables or {}})
    assert response.status_code == 200, response.text
    return response.json()


def data(client, query, variables=None):
    envelope = request(client, query, variables)
    assert not envelope.get("errors"), envelope
    return envelope["data"]


def success(payload):
    assert payload["errors"] == [], payload
    assert payload["product"] is not None
    return payload


def failure(payload, code, field=None):
    assert payload["product"] is None
    assert payload["movement"] is None
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["code"] == code, payload
    assert payload["errors"][0]["message"]
    if field is not None:
        assert payload["errors"][0]["field"] == field


@pytest.fixture
def api_product(client):
    counter = 0

    def create(**changes):
        nonlocal counter
        counter += 1
        values = {"sku": f"GRAPH-{counter}", "name": f"Product {counter:02}", "category": "General", "unitPriceMinor": 29, "lowStockThreshold": 3, "openingQuantity": 10}
        values.update(changes)
        return success(data(client, CREATE, {"input": values})["createProduct"])
    return create


def snapshot(client, id):
    return data(client, SNAPSHOT, {"id": id})


def edit_input(product, **changes):
    values = {key: product[key] for key in ("id", "name", "category", "unitPriceMinor", "lowStockThreshold")}
    values.update(changes)
    return values


def movement(client, id, operation, quantity, reason="Integration test"):
    adjustment = operation == "adjustStock"
    query = f"mutation Change($input: {'AdjustmentInput' if adjustment else 'StockInput'}!) {{ {operation}(input: $input) {{ {RESULT} }} }}"
    values = {"productId": id, "reason": reason, "countedQuantity" if adjustment else "quantity": quantity}
    return request(client, query, {"input": values})


@pytest.mark.parametrize("opening", [0, 7])
def test_creation_records_one_opening_movement(client, api_product, opening):
    result = api_product(sku="  mixed-sku  ", openingQuantity=opening)
    product = result["product"]
    assert product["sku"] == "MIXED-SKU"
    assert product["currentStock"] == opening
    timestamp = datetime.fromisoformat(product["createdAt"])
    assert timestamp.utcoffset().total_seconds() == 0
    state = snapshot(client, product["id"])
    assert state["stockMovements"]["items"] == [result["movement"]]
    assert result["movement"]["quantityChange"] == opening
    assert result["movement"]["movementType"] == "OPENING"
    assert result["movement"]["productId"] == product["id"]


def test_complete_lifecycle_preserves_exact_history_and_read_only_archive(client, api_product):
    product = api_product()["product"]
    id = product["id"]
    opening = snapshot(client, id)["stockMovements"]
    edited = success(data(client, UPDATE, {"input": edit_input(product, name="Renamed product", category="Office", unitPriceMinor=101, lowStockThreshold=4)})["updateProduct"])
    assert edited["product"]["sku"] == product["sku"]
    assert edited["product"]["createdAt"] == product["createdAt"]
    assert edited["product"]["currentStock"] == 10
    assert edited["movement"] is None
    assert snapshot(client, id)["stockMovements"]["items"][0]["quantityChange"] == opening["items"][0]["quantityChange"]
    before = snapshot(client, id)
    failure(data(client, ARCHIVE, {"id": id})["archiveProduct"], "NONZERO_STOCK")
    assert snapshot(client, id) == before

    for operation, quantity, balance, delta, reason in [
        ("receiveStock", 5, 15, 5, "Delivery received"),
        ("issueStock", 3, 12, -3, "Shop use"),
        ("adjustStock", 17, 17, 5, "Count found more units"),
        ("adjustStock", 0, 0, -17, "Damaged goods removed"),
    ]:
        result = success(movement(client, id, operation, quantity, reason)["data"][operation])
        assert result["product"]["currentStock"] == balance
        assert result["movement"]["quantityChange"] == delta
        assert result["movement"]["reason"] == reason
    before_archive = snapshot(client, id)["stockMovements"]
    assert before_archive["totalCount"] == 5
    assert [row["quantityChange"] for row in before_archive["items"]] == [-17, 5, -3, 5, 10]
    assert sum(row["quantityChange"] for row in before_archive["items"]) == 0
    archived = success(data(client, ARCHIVE, {"id": id})["archiveProduct"])["product"]
    assert archived["archivedAt"] is not None
    after_archive = snapshot(client, id)
    assert after_archive["stockMovements"] == before_archive
    assert after_archive["dashboard"] == {"productCount": 0, "totalUnits": "0", "lowStockCount": 0}
    failure(data(client, UPDATE, {"input": edit_input(archived, name="Cannot edit")})["updateProduct"], "PRODUCT_ARCHIVED")
    for operation in ("receiveStock", "issueStock", "adjustStock"):
        failure(movement(client, id, operation, 1)["data"][operation], "PRODUCT_ARCHIVED")
    failure(data(client, ARCHIVE, {"id": id})["archiveProduct"], "PRODUCT_ARCHIVED")
    assert snapshot(client, id) == after_archive


@pytest.mark.parametrize("archived", [False, True], ids=["active", "archived"])
def test_duplicate_sku_never_creates_product_or_opening_movement(client, api_product, archived):
    original = api_product(sku="RESERVED", openingQuantity=0)["product"]
    if archived:
        success(data(client, ARCHIVE, {"id": original["id"]})["archiveProduct"])
    before = snapshot(client, original["id"])
    values = {"sku": "  reserved  ", "name": "Duplicate", "category": "Other", "unitPriceMinor": 101, "lowStockThreshold": 0, "openingQuantity": 99}
    failure(data(client, CREATE, {"input": values})["createProduct"], "DUPLICATE_SKU", "sku")
    assert snapshot(client, original["id"]) == before
    assert data(client, "{ products(filter: {archiveStatus: ALL}) { totalCount } }")["products"]["totalCount"] == 1


@pytest.mark.parametrize("field,value,error_field", [
    ("name", "   ", "name"), ("name", "N" * 161, "name"),
    ("category", "", "category"), ("category", "C" * 81, "category"),
    ("unitPriceMinor", -1, "unitPriceMinor"), ("lowStockThreshold", -1, "lowStockThreshold"),
    ("openingQuantity", -1, "openingQuantity"), ("sku", " ", "sku"),
    ("sku", "bad sku", "sku"), ("sku", "S" * 65, "sku"),
])
def test_invalid_create_inputs_are_structured_and_do_not_write(client, field, value, error_field):
    values = {"sku": "VALID", "name": "Valid name", "category": "General", "unitPriceMinor": 29, "lowStockThreshold": 0, "openingQuantity": 0, field: value}
    failure(data(client, CREATE, {"input": values})["createProduct"], "INVALID_INPUT", error_field)
    state = data(client, "{ products { totalCount } stockMovements { totalCount } dashboard { productCount totalUnits lowStockCount } }")
    assert state["products"]["totalCount"] == state["stockMovements"]["totalCount"] == 0
    assert state["dashboard"]["totalUnits"] == "0"


@pytest.mark.parametrize("field,value", [("unitPriceMinor", 0.29), ("unitPriceMinor", "29"), ("unitPriceMinor", 2147483648), ("openingQuantity", 1.5), ("openingQuantity", True), ("name", None)])
def test_graphql_rejects_incorrect_input_types_before_execution(client, field, value):
    values = {"sku": "VALID", "name": "Name", "category": "General", "unitPriceMinor": 29, "lowStockThreshold": 0, "openingQuantity": 0, field: value}
    result = request(client, CREATE, {"input": values})
    assert result.get("errors")
    assert data(client, "{ products { totalCount } stockMovements { totalCount } }") == {"products": {"totalCount": 0}, "stockMovements": {"totalCount": 0}}


@pytest.mark.parametrize("changes,field", [({"name": " "}, "name"), ({"category": " "}, "category"), ({"unitPriceMinor": -1}, "unitPriceMinor"), ({"lowStockThreshold": -1}, "lowStockThreshold")])
def test_invalid_edits_leave_all_fields_and_history_unchanged(client, api_product, changes, field):
    product = api_product()["product"]
    before = snapshot(client, product["id"])
    failure(data(client, UPDATE, {"input": edit_input(product, **changes)})["updateProduct"], "INVALID_INPUT", field)
    assert snapshot(client, product["id"]) == before


@pytest.mark.parametrize("operation,quantity,reason,code,field", [
    ("receiveStock", 0, "Delivery", "INVALID_INPUT", "quantity"),
    ("receiveStock", -1, "Delivery", "INVALID_INPUT", "quantity"),
    ("issueStock", 11, "Shop use", "INSUFFICIENT_STOCK", "quantity"),
    ("issueStock", 0, "Shop use", "INVALID_INPUT", "quantity"),
    ("issueStock", -1, "Shop use", "INVALID_INPUT", "quantity"),
    ("adjustStock", -1, "Count", "INVALID_INPUT", "countedQuantity"),
    ("adjustStock", 10, "Count", "NO_CHANGE", "countedQuantity"),
    ("adjustStock", 9, "  ", "INVALID_INPUT", "reason"),
    ("adjustStock", 9, "R" * 501, "INVALID_INPUT", "reason"),
    ("receiveStock", 2147483647, "Overflow", "INVALID_INPUT", "quantity"),
])
def test_rejected_stock_operations_leave_exact_snapshot_unchanged(client, api_product, operation, quantity, reason, code, field):
    id = api_product()["product"]["id"]
    before = snapshot(client, id)
    failure(movement(client, id, operation, quantity, reason)["data"][operation], code, field)
    assert snapshot(client, id) == before


@pytest.mark.parametrize("minor", [0, 1, 29, 101, 2147483647])
def test_prices_round_trip_as_integer_minor_units_and_exact_csv(client, api_product, database, minor):
    product = api_product(unitPriceMinor=minor)["product"]
    assert snapshot(client, product["id"])["product"]["unitPriceMinor"] == minor
    updated = success(data(client, UPDATE, {"input": edit_input(product, unitPriceMinor=minor)})["updateProduct"])
    assert updated["product"]["unitPriceMinor"] == minor
    with database.read() as session:
        value, storage_type = session.execute(text("SELECT unit_price_minor, typeof(unit_price_minor) FROM products WHERE id = :id"), {"id": int(product["id"])}).one()
    assert value == minor and storage_type == "integer"
    exported = data(client, "{ inventoryCsv { content } }")["inventoryCsv"]["content"]
    row = next(csv.DictReader(io.StringIO(exported)))
    assert row["Unit price"] == format(Decimal(minor) / 100, ".2f")


def test_concurrent_issues_return_exact_winner_and_loser_payloads(client, api_product):
    id = api_product(openingQuantity=5)["product"]["id"]
    barrier = Barrier(6)

    def issue():
        barrier.wait(timeout=10)
        return movement(client, id, "issueStock", 2)["data"]["issueStock"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: issue(), range(6)))
    assert len([result for result in results if not result["errors"]]) == 2
    for result in results:
        if result["errors"]:
            failure(result, "INSUFFICIENT_STOCK", "quantity")
    state = snapshot(client, id)
    assert state["product"]["currentStock"] == 1
    assert state["stockMovements"]["totalCount"] == 3
    assert sum(row["quantityChange"] for row in state["stockMovements"]["items"]) == 1


@pytest.mark.parametrize("operation", ["createProduct", "receiveStock"])
def test_database_failure_rolls_back_complete_graphql_mutation(client, api_product, database, operation):
    existing = api_product()["product"]
    before = snapshot(client, existing["id"])
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TRIGGER reject_test_movement BEFORE INSERT ON stock_movements BEGIN SELECT RAISE(ABORT, 'Injected insert failure'); END")
    if operation == "createProduct":
        values = {"sku": "ROLLBACK", "name": "Must not persist", "category": "Other", "unitPriceMinor": 123, "lowStockThreshold": 1, "openingQuantity": 20}
        payload = data(client, CREATE, {"input": values})[operation]
    else:
        payload = movement(client, existing["id"], operation, 2)["data"][operation]
    failure(payload, "INVALID_INPUT")
    assert snapshot(client, existing["id"]) == before
    assert data(client, "{ products { totalCount } }")["products"]["totalCount"] == 1
    # The connection remains usable after rollback, not in a failed session state.
    with database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER reject_test_movement")
    success(movement(client, existing["id"], "receiveStock", 1)["data"]["receiveStock"])


def test_filtered_product_pagination_and_dashboard_track_stock_changes(client, api_product):
    first = api_product(name="A pen", category="Office", openingQuantity=3)["product"]
    second = api_product(name="B pencil", category="office", openingQuantity=7)["product"]
    api_product(name="100% cotton", category="Clothing", openingQuantity=0)
    archived = api_product(name="Archived pen", category="Office", openingQuantity=0)["product"]
    success(data(client, ARCHIVE, {"id": archived["id"]})["archiveProduct"])
    query = f"query Page($filter: ProductFilter!, $offset: Int!) {{ products(filter: $filter, limit: 1, offset: $offset) {{ totalCount items {{ {PRODUCT} }} }} }}"
    filters = {"search": "PEN", "category": "OFFICE"}
    pages = [data(client, query, {"filter": filters, "offset": offset})["products"] for offset in range(3)]
    assert [page["totalCount"] for page in pages] == [2, 2, 2]
    assert [page["items"][0]["id"] for page in pages[:2]] == [first["id"], second["id"]]
    assert pages[2]["items"] == []
    assert data(client, query, {"filter": {"search": "%"}, "offset": 0})["products"]["totalCount"] == 1
    assert data(client, query, {"filter": {"lowStockOnly": True}, "offset": 0})["products"]["totalCount"] == 2
    assert data(client, query, {"filter": {"archiveStatus": "ARCHIVED"}, "offset": 0})["products"]["items"][0]["id"] == archived["id"]
    assert snapshot(client, first["id"])["dashboard"] == {"productCount": 3, "totalUnits": "10", "lowStockCount": 2}
    success(movement(client, first["id"], "receiveStock", 1)["data"]["receiveStock"])
    success(movement(client, second["id"], "issueStock", 4)["data"]["issueStock"])
    assert snapshot(client, first["id"])["dashboard"] == {"productCount": 3, "totalUnits": "7", "lowStockCount": 2}


def test_history_date_boundaries_and_stable_pagination(client, api_product, database):
    id = api_product(openingQuantity=0)["product"]["id"]
    dates = ["2001-01-01T23:59:59.999999", "2001-01-02T00:00:00", "2001-01-02T23:59:59.999999", "2001-01-02T23:59:59.999999", "2001-01-03T00:00:00"]
    with database.write() as session:
        for index, date in enumerate(dates):
            session.add(StockMovement(product_id=int(id), movement_type="RECEIVED", quantity_change=1, reason=f"Boundary {index}", created_at=datetime.fromisoformat(date).replace(tzinfo=timezone.utc)))
    query = f"query History($filter: MovementFilter!, $offset: Int!) {{ stockMovements(filter: $filter, limit: 1, offset: $offset) {{ totalCount items {{ {MOVEMENT} }} }} }}"
    filters = {"productId": id, "movementType": "RECEIVED", "fromDate": "2001-01-02", "toDate": "2001-01-02"}
    pages = [data(client, query, {"filter": filters, "offset": index})["stockMovements"] for index in range(4)]
    assert [page["totalCount"] for page in pages] == [3] * 4
    assert [page["items"][0]["reason"] for page in pages[:3]] == ["Boundary 3", "Boundary 2", "Boundary 1"]
    assert len({page["items"][0]["id"] for page in pages[:3]}) == 3
    assert pages[3]["items"] == []
    bad = request(client, query, {"filter": {"fromDate": "2001-01-03", "toDate": "2001-01-02"}, "offset": 0})
    assert bad["errors"][0]["extensions"] == {"code": "INVALID_INPUT", "field": "fromDate"}


@pytest.mark.parametrize("root", ["products", "stockMovements"])
@pytest.mark.parametrize("arguments,field", [("limit: 0", "limit"), ("limit: 101", "limit"), ("offset: -1", "offset")])
def test_invalid_pagination_returns_useful_graphql_errors(client, root, arguments, field):
    result = request(client, f"{{ {root}({arguments}) {{ totalCount }} }}")
    assert result["errors"][0]["extensions"] == {"code": "INVALID_INPUT", "field": field}


def test_csv_exports_all_filtered_rows_with_exact_current_balances(client, api_product):
    expected = {}
    for index in range(23):
        product = api_product(name=f'Item {index:02}, "quoted"', category="Export", unitPriceMinor=29 + index, openingQuantity=index)["product"]
        expected[product["sku"]] = product
    excluded = api_product(category="Excluded")["product"]
    first = next(iter(expected.values()))
    success(movement(client, first["id"], "receiveStock", 5)["data"]["receiveStock"])
    expected[first["sku"]]["currentStock"] = 5
    first_page = data(client, '{ products(filter: {category: "Export"}, limit: 20) { totalCount items { id } } }')["products"]
    assert len(first_page["items"]) == 20
    csv_data = data(client, '{ inventoryCsv(filter: {category: "Export"}) { filename contentType content } }')["inventoryCsv"]
    assert csv_data["filename"].endswith(".csv")
    assert csv_data["contentType"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(csv_data["content"])))
    assert len(rows) == first_page["totalCount"] == 23
    assert excluded["sku"] not in {row["SKU"] for row in rows}
    for row in rows:
        product = expected[row["SKU"]]
        assert row == {"SKU": product["sku"], "Name": product["name"], "Category": "Export", "Unit price": format(Decimal(product["unitPriceMinor"]) / 100, ".2f"), "Current stock": str(product["currentStock"]), "Low-stock threshold": "3", "Low stock": "Yes" if product["currentStock"] <= 3 else "No", "Archived": "No"}


def test_concurrent_duplicate_creation_only_writes_one_opening_balance(client):
    values = {"sku": "CONCURRENT", "name": "One product", "category": "General", "unitPriceMinor": 29, "lowStockThreshold": 3, "openingQuantity": 7}
    barrier = Barrier(4)

    def create():
        barrier.wait(timeout=10)
        return data(client, CREATE, {"input": values})["createProduct"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(create) for _ in range(4)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(not result["errors"] for result in results) == 1
    for result in results:
        if result["errors"]:
            failure(result, "DUPLICATE_SKU", "sku")
    assert data(client, "{ products { totalCount } stockMovements { totalCount } dashboard { totalUnits } }") == {"products": {"totalCount": 1}, "stockMovements": {"totalCount": 1}, "dashboard": {"totalUnits": "7"}}


def test_aggregate_dashboard_total_exceeds_int_without_losing_precision(client, api_product):
    api_product(openingQuantity=2147483647)
    api_product(openingQuantity=2147483647)
    assert data(client, "{ dashboard { totalUnits productCount lowStockCount } }")["dashboard"] == {"totalUnits": "4294967294", "productCount": 2, "lowStockCount": 0}
