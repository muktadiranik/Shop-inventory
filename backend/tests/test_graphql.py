from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services import products, stock

CREATE = """mutation Create($input: CreateProductInput!) {
  createProduct(input: $input) {
    product { id sku name unitPriceMinor currentStock isLowStock }
    movement { movementType quantityChange }
    errors { code field message }
  }
}"""


def gql(client, query, variables=None):
    response = client.post("/graphql", json={"query": query, "variables": variables or {}})
    assert response.status_code == 200, response.text
    return response.json()


def create_input(**updates):
    values = {"sku": "API-1", "name": "API product", "category": "General", "unitPriceMinor": 29, "lowStockThreshold": 3, "openingQuantity": 3}
    values.update(updates)
    return values


def test_create_and_query(client):
    result = gql(client, CREATE, {"input": create_input()})
    assert "errors" not in result
    payload = result["data"]["createProduct"]
    assert payload["errors"] == []
    assert payload["product"]["unitPriceMinor"] == 29
    assert payload["product"]["isLowStock"]
    assert payload["movement"] == {"movementType": "OPENING", "quantityChange": 3}
    data = gql(client, "{ dashboard { productCount totalUnits lowStockCount } products(limit: 1) { totalCount items { sku } } }")["data"]
    assert data["dashboard"] == {"productCount": 1, "totalUnits": "3", "lowStockCount": 1}
    assert data["products"]["items"][0]["sku"] == "API-1"


def test_structured_errors_and_graphql_validation(client):
    gql(client, CREATE, {"input": create_input()})
    duplicate = gql(client, CREATE, {"input": create_input(sku="api-1")})["data"]["createProduct"]
    assert duplicate["product"] is None
    assert duplicate["errors"][0]["code"] == "DUPLICATE_SKU"
    invalid = gql(client, CREATE, {"input": create_input(sku="NEW", unitPriceMinor=-1)})["data"]["createProduct"]
    assert invalid["errors"][0]["field"] == "unitPriceMinor"
    invalid_graphql = gql(client, CREATE, {"input": create_input(unitPriceMinor=1.2)})
    assert invalid_graphql["errors"]
    assert gql(client, "{ products(limit: 101) { totalCount } }")["errors"][0]["extensions"]["code"] == "INVALID_INPUT"


def test_stock_mutations_and_missing_reason(client, database, make_product):
    product = make_product(opening_quantity=2)
    issue = "mutation Issue($input: StockInput!) { issueStock(input: $input) { product { currentStock } errors { code field } } }"
    assert gql(client, issue, {"input": {"productId": product["id"], "quantity": 3, "reason": "Shop use"}})["data"]["issueStock"]["errors"][0]["code"] == "INSUFFICIENT_STOCK"
    adjust = "mutation Adjust($input: AdjustmentInput!) { adjustStock(input: $input) { product { currentStock } movement { quantityChange } errors { code field } } }"
    missing = gql(client, adjust, {"input": {"productId": product["id"], "countedQuantity": 0, "reason": " "}})["data"]["adjustStock"]
    assert missing["errors"][0]["field"] == "reason"
    success = gql(client, adjust, {"input": {"productId": product["id"], "countedQuantity": 0, "reason": "Damaged goods"}})["data"]["adjustStock"]
    assert success["product"]["currentStock"] == 0
    assert success["movement"]["quantityChange"] == -2


def test_archive_and_export_through_graphql(client, make_product):
    product = make_product(opening_quantity=0)
    result = gql(client, "mutation Archive($id: ID!) { archiveProduct(id: $id) { product { archivedAt } errors { code } } }", {"id": product["id"]})
    assert result["data"]["archiveProduct"]["product"]["archivedAt"]
    result = gql(client, "{ inventoryCsv(filter: {archiveStatus: ALL}) { content filename } stockMovements { totalCount } }")
    assert product["sku"] in result["data"]["inventoryCsv"]["content"]
    assert result["data"]["stockMovements"]["totalCount"] == 1


def test_concurrent_http_issues(client, make_product, database):
    product = make_product(opening_quantity=1)
    barrier = Barrier(2)
    query = "mutation Issue($input: StockInput!) { issueStock(input: $input) { product { currentStock } errors { code } } }"

    def issue():
        barrier.wait(timeout=10)
        return gql(client, query, {"input": {"productId": product["id"], "quantity": 1, "reason": "Concurrent request"}})["data"]["issueStock"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(issue) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(not result["errors"] for result in results) == 1
    assert products.get_product(database, product["id"])["current_stock"] == 0
    assert stock.list_movements(database)["total_count"] == 2


def test_local_api_protection(client):
    assert client.post("/graphql", json={"query": "{ dashboard { productCount } }"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/graphql", content="query=test", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post("/graphql", json={"query": "{ dashboard { productCount } }"}, headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/graphql", params={"query": "mutation { archiveProduct(id: 1) { errors { code } } }"}).status_code in {400, 404, 405}


def test_frontend_serving_and_unknown_asset(database, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>React frontend</html>", encoding="utf-8")
    (dist / "assets/app.js").write_text("console.log('ok')", encoding="utf-8")
    with TestClient(create_app(database.path, dist)) as client:
        assert "React frontend" in client.get("/products/1/edit").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/missing.js").status_code == 404
        assert gql(client, "{ dashboard { productCount } }")["data"]


def test_startup_requires_migrations(tmp_path):
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        with TestClient(create_app(tmp_path / "new.sqlite3")):
            pass


def test_missing_and_out_of_range_product_ids(client):
    assert gql(client, '{ product(id: "999") { id } }')["data"]["product"] is None
    result = gql(client, 'mutation { archiveProduct(id: "999") { errors { code } } }')
    assert result["data"]["archiveProduct"]["errors"][0]["code"] == "PRODUCT_NOT_FOUND"
    result = gql(client, '{ product(id: "999999999999999999999999999") { id } }')
    assert result["errors"][0]["extensions"]["code"] == "INVALID_INPUT"
