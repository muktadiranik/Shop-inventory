"""Optional real-browser check. Uses a temporary database, never the shop database.

From backend: python browser_smoke.py (after installing the browser extra/Chromium
and building frontend). The script starts and stops its own local server.
"""
import csv
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BACKEND = Path(__file__).resolve().parent


def check_accessibility(page):
    page.add_script_tag(path=str(BACKEND.parent / "frontend/node_modules/axe-core/axe.min.js"))
    violations = page.evaluate("""async () => {
      const result = await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa']});
      return result.violations.map(item => ({id: item.id, nodes: item.nodes.map(node => ({target: node.target, summary: node.failureSummary}))}));
    }""")
    assert not violations, json.dumps(violations, indent=2)


def api(page, base_url, query, variables=None):
    response = page.request.post(f"{base_url}/graphql", data={"query": query, "variables": variables or {}})
    assert response.ok, response.text()
    result = response.json()
    assert not result.get("errors"), result
    return result["data"]


def check_viewport(page):
    dimensions = page.evaluate("""() => ({
      width: innerWidth, scroll: document.documentElement.scrollWidth,
      containers: ['.sidebar', '.sidebar nav', '.workspace', '.main-content', '.page-heading', '.panel', '.filter-bar', '.filter-controls', '.pagination-bar'].map(selector => {
        const element = document.querySelector(selector);
        return element ? {selector, width: element.getBoundingClientRect().width, scroll: element.scrollWidth} : null;
      }),
      outside: Array.from(document.querySelectorAll('body *')).filter(element => !element.closest('.table-responsive') && element.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(element => ({tag: element.tagName, class: element.className, right: element.getBoundingClientRect().right, position: getComputedStyle(element).position}))
    })""")
    assert dimensions["scroll"] <= dimensions["width"] + 1, dimensions


def check_additional_workflows(page, base_url, downloads):
    """Regression scenarios missed by the original single-product happy path."""
    create = """mutation Seed($input: CreateProductInput!) {
      createProduct(input: $input) { product { id sku name } errors { code message } }
    }"""
    products = []
    for index in range(25):
        values = {"sku": f"PAGE-{index + 1:02}", "name": f"Page item {index + 1:02}" + (', "quoted"' if index == 0 else ''), "category": "Page A" if index < 22 else "Page B", "unitPriceMinor": 29 + index, "lowStockThreshold": 3, "openingQuantity": index}
        payload = api(page, base_url, create, {"input": values})["createProduct"]
        assert not payload["errors"], payload
        products.append({**values, **payload["product"]})

    # Returning to a valid second page must not use the previous filtered count
    # to incorrectly redirect the browser back to page one.
    page.goto(f"{base_url}/products?page=2")
    expect(page.get_by_role("link", name="Page item 21", exact=True)).to_be_visible()
    page.get_by_role("searchbox", name="Search products by SKU or name").fill("Page item 01")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.get_by_role("link", name=products[0]["name"], exact=True)).to_be_visible()
    expect(page.get_by_role("navigation", name="Pagination")).to_contain_text("1–1 of 1")
    page.go_back()
    expect(page).to_have_url(re.compile(r"/products\?page=2$"))
    expect(page.get_by_role("link", name="Page item 21", exact=True)).to_be_visible()
    expect(page.get_by_role("navigation", name="Pagination")).to_contain_text("21–25 of 25")

    # The export is filtered, exact, correctly quoted, and NOT just this page.
    page.goto(f"{base_url}/products?category=Page+A")
    expect(page.get_by_role("navigation", name="Pagination")).to_contain_text("1–20 of 22")
    with page.expect_download() as info:
        page.get_by_role("button", name="↓ Export CSV", exact=True).click()
    destination = downloads / "filtered-multipage.csv"
    info.value.save_as(destination)
    rows = list(csv.DictReader(io.StringIO(destination.read_text(encoding="utf-8-sig"))))
    assert len(rows) == 22
    for index, row in enumerate(rows):
        assert row == {"SKU": products[index]["sku"], "Name": products[index]["name"], "Category": "Page A", "Unit price": f"0.{29 + index:02}", "Current stock": str(index), "Low-stock threshold": "3", "Low stock": "Yes" if index <= 3 else "No", "Archived": "No"}

    # Confirm errors come from the real API and are tied to accessible fields.
    page.goto(f"{base_url}/products/new")
    page.get_by_label("SKU", exact=True).fill("UNUSED")
    page.get_by_label("Product name", exact=True).fill(" ")
    page.get_by_label("Category", exact=True).fill("Validation")
    page.get_by_label("Unit price", exact=True).fill("0.29")
    page.get_by_role("button", name="Create product", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Enter 1–160 characters")
    expect(page.get_by_label("Product name", exact=True)).to_have_attribute("aria-invalid", "true")
    expect(page.get_by_label("Product name", exact=True)).to_have_attribute("aria-describedby", re.compile("error"))
    page.get_by_label("Product name", exact=True).fill("Duplicate product")
    page.get_by_label("SKU", exact=True).fill("page-01")
    page.get_by_role("button", name="Create product", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("This SKU is already in use")
    expect(page.get_by_label("SKU", exact=True)).to_have_attribute("aria-invalid", "true")
    expect(page.get_by_label("SKU", exact=True)).to_have_value("page-01")
    check_accessibility(page)

    detail = f"{base_url}/products/{products[0]['id']}"
    state_query = """query Check($id: ID!) {
      product(id: $id) { currentStock }
      stockMovements(filter: {productId: $id}) { totalCount items { reason quantityChange } }
    }"""
    for width in (1440, 390):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(detail)
        expect(page.get_by_role("heading", name=products[0]["name"], exact=True)).to_be_visible()
        before = api(page, base_url, state_query, {"id": products[0]["id"]})

        def fail_receipt(route):
            if "mutation ReceiveStock" in route.request.post_data_json.get("query", ""):
                route.abort()
            else:
                route.continue_()
        page.route("**/graphql", fail_receipt)
        page.get_by_label("Quantity", exact=True).fill("1")
        page.get_by_label("Reason", exact=True).fill(f"Receipt at {width}px")
        page.get_by_role("button", name="Receive stock", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Cannot reach the inventory server")
        expect(page.get_by_label("Quantity", exact=True)).to_have_value("1")
        assert api(page, base_url, state_query, {"id": products[0]["id"]}) == before
        page.unroute("**/graphql", fail_receipt)
        page.get_by_role("button", name="Receive stock", exact=True).click()
        expect(page.locator(".product-summary .summary-number")).to_have_text("1")
        expect(page.get_by_role("cell", name=f"Receipt at {width}px", exact=True)).to_be_visible()
        after_receive = api(page, base_url, state_query, {"id": products[0]["id"]})
        assert after_receive["stockMovements"]["totalCount"] == before["stockMovements"]["totalCount"] + 1

        def fail_issue(route):
            if "mutation IssueStock" in route.request.post_data_json.get("query", ""):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"errors": [{"message": "Simulated mutation error"}]}))
            else:
                route.continue_()
        page.route("**/graphql", fail_issue)
        page.get_by_label("Movement type", exact=True).select_option("ISSUED")
        page.get_by_label("Quantity", exact=True).fill("1")
        page.get_by_label("Reason", exact=True).fill(f"Issue at {width}px")
        page.get_by_role("button", name="Issue stock", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Simulated mutation error")
        assert api(page, base_url, state_query, {"id": products[0]["id"]}) == after_receive
        page.unroute("**/graphql", fail_issue)
        page.get_by_role("button", name="Issue stock", exact=True).click()
        expect(page.locator(".product-summary .summary-number")).to_have_text("0")
        expect(page.get_by_role("cell", name=f"Issue at {width}px", exact=True)).to_be_visible()
        check_viewport(page)
        check_accessibility(page)

        page.goto(f"{base_url}/products/new")
        expect(page.get_by_label("Opening stock", exact=True)).to_be_visible()
        check_viewport(page)
        check_accessibility(page)
        page.goto(f"{base_url}/products")
        expect(page.get_by_role("link", name=products[0]["name"], exact=True)).to_be_visible()
        check_viewport(page)
        check_accessibility(page)

    page.goto(base_url)
    expect(page.locator(".summary-card").filter(has=page.get_by_text("Active products", exact=True)).locator(".summary-number")).to_have_text("25")
    expect(page.locator(".summary-card").filter(has=page.get_by_text("Total units on hand", exact=True)).locator(".summary-number")).to_have_text("300")
    expect(page.locator(".summary-card").filter(has=page.get_by_text("Products running low", exact=True)).locator(".summary-number")).to_have_text("4")
    # JSON can parse successfully but still not be a valid GraphQL envelope.
    page.route("**/graphql", lambda route: route.fulfill(status=200, content_type="application/json", body="null"))
    page.reload()
    expect(page.get_by_role("alert")).to_contain_text("invalid GraphQL response")
    page.unroute("**/graphql")
    page.get_by_role("button", name="Try again", exact=True).click()
    expect(page.locator(".summary-card").filter(has=page.get_by_text("Active products", exact=True)).locator(".summary-number")).to_have_text("25")


def run_browser_check(base_url, downloads):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors = []
        mutations = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def record_request(request):
            if request.method == "POST" and request.url.endswith("/graphql"):
                body = request.post_data_json
                if body.get("query", "").startswith("mutation"):
                    mutations.append(body)
        page.on("request", record_request)
        page.goto(base_url)
        expect(page.get_by_role("heading", name="Inventory overview")).to_be_visible()
        expect(page.get_by_text("Welcome to your stockroom")).to_be_visible()
        check_accessibility(page)
        page.get_by_role("link", name="+ Add product").click()
        expect(page.get_by_label("Opening stock", exact=True)).to_be_visible()
        check_accessibility(page)
        page.get_by_label("SKU", exact=True).fill("browser-1")
        page.get_by_label("Product name", exact=True).fill("Everyday notebook")
        page.get_by_label("Category", exact=True).fill("Paper")
        page.get_by_label("Unit price", exact=True).fill("0.29")
        page.get_by_label("Low-stock threshold", exact=True).fill("3")
        page.get_by_label("Opening stock", exact=True).fill("10")
        page.get_by_role("button", name="Create product", exact=True).click()
        expect(page.get_by_role("heading", name="Everyday notebook", exact=True)).to_be_visible()
        expect(page.get_by_text("10", exact=True)).to_be_visible()
        detail_url = page.url
        check_accessibility(page)

        # A rapid double click must create only one movement.
        page.get_by_label("Quantity", exact=True).fill("5")
        page.get_by_label("Reason", exact=True).fill("Delivery received")
        page.get_by_role("button", name="Receive stock", exact=True).dblclick()
        expect(page.get_by_text("15", exact=True)).to_be_visible()
        assert sum("mutation ReceiveStock" in mutation["query"] for mutation in mutations) == 1

        page.get_by_label("Movement type", exact=True).select_option("ISSUED")
        page.get_by_label("Quantity", exact=True).fill("100")
        page.get_by_role("button", name="Issue stock", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Only 15 units are available")
        page.get_by_label("Quantity", exact=True).fill("7")
        page.get_by_role("button", name="Issue stock", exact=True).click()
        expect(page.get_by_text("8", exact=True)).to_be_visible()

        page.get_by_label("Movement type", exact=True).select_option("ADJUSTMENT")
        page.get_by_label("Counted quantity", exact=True).fill("2")
        page.get_by_label("Reason", exact=True).fill("Physical count")
        page.get_by_role("button", name="Adjust stock", exact=True).click()
        expect(page.get_by_text("2", exact=True)).to_be_visible()
        expect(page.get_by_text("Low stock", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Archive product", exact=True)).to_be_disabled()

        page.get_by_role("link", name="Edit product", exact=True).click()
        page.get_by_label("Unit price", exact=True).fill("1.01")
        page.get_by_role("button", name="Save changes", exact=True).click()
        expect(page.get_by_text("1.01", exact=True)).to_be_visible()
        page.get_by_role("link", name="Products", exact=True).click()
        page.get_by_role("searchbox", name="Search products by SKU or name").fill("notebook")
        page.get_by_role("button", name="Search", exact=True).click()
        page.get_by_label("Category", exact=True).select_option("Paper")
        page.get_by_label("Low stock only", exact=True).check()
        expect(page.get_by_role("link", name="Everyday notebook", exact=True)).to_be_visible()
        check_accessibility(page)
        with page.expect_download() as info:
            page.get_by_role("button", name="↓ Export CSV", exact=True).click()
        download = info.value
        download.save_as(downloads / download.suggested_filename)
        content = (downloads / download.suggested_filename).read_text(encoding="utf-8-sig")
        assert "BROWSER-1" in content and "1.01" in content

        page.goto(detail_url)
        page.reload()  # Verify production SPA deep links.
        page.get_by_label("Movement type", exact=True).select_option("ADJUSTMENT")
        page.get_by_label("Counted quantity", exact=True).fill("0")
        page.get_by_label("Reason", exact=True).fill("Damaged stock removed")
        page.get_by_role("button", name="Adjust stock", exact=True).click()
        expect(page.get_by_text("0", exact=True)).to_be_visible()
        page.get_by_role("button", name="Archive product", exact=True).click()
        page.get_by_role("button", name="Confirm archive", exact=True).click()
        expect(page.get_by_text("Archived", exact=True)).to_be_visible()
        expect(page.get_by_label("Movement type", exact=True)).to_have_count(0)
        expect(page.get_by_role("cell", name="Physical count", exact=True)).to_be_visible()

        page.get_by_role("link", name="Products", exact=True).click()
        page.get_by_label("Show", exact=True).select_option("ARCHIVED")
        expect(page.get_by_role("link", name="Everyday notebook", exact=True)).to_be_visible()
        page.get_by_role("link", name="Movement history", exact=True).click()
        page.get_by_label("Product SKU or name", exact=True).fill("BROWSER-1")
        page.get_by_role("button", name="Apply filters", exact=True).click()
        expect(page.get_by_role("cell", name="Damaged stock removed", exact=True)).to_be_visible()
        check_accessibility(page)

        # Mobile layout must not cause whole-document horizontal scrolling.
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(detail_url)
        expect(page.get_by_role("heading", name="Everyday notebook", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        check_accessibility(page)

        # Network and GraphQL failures remain visible and recoverable.
        page.route("**/graphql", lambda route: route.abort())
        page.goto(base_url)
        expect(page.get_by_role("alert")).to_contain_text("Cannot reach the inventory server")
        page.unroute("**/graphql")
        page.get_by_role("button", name="Try again", exact=True).click()
        expect(page.get_by_text("Welcome to your stockroom")).to_be_visible()
        page.route("**/graphql", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"errors": [{"message": "Simulated GraphQL failure"}]})))
        page.reload()
        expect(page.get_by_role("alert")).to_contain_text("Simulated GraphQL failure")
        page.unroute("**/graphql")
        check_additional_workflows(page, base_url, downloads)
        assert not errors, errors
        browser.close()


def main():
    if not (BACKEND.parent / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend first: from frontend, run npm run build")
    parent = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Temp/opencode"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="inventory-browser-", dir=parent) as temporary:
        temporary = Path(temporary)
        env = {**os.environ, "INVENTORY_DATABASE": str(temporary / "test.sqlite3")}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        with (temporary / "server.log").open("w+", encoding="utf-8") as log:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"], cwd=BACKEND, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        with urlopen(base_url, timeout=1) as response:
                            if response.status == 200:
                                break
                    except (URLError, TimeoutError):
                        if server.poll() is not None:
                            raise RuntimeError("Browser test server exited early")
                        time.sleep(.1)
                else:
                    raise RuntimeError("Browser test server did not become ready")
                run_browser_check(base_url, temporary)
                print("Browser checks passed: inventory lifecycle; API field validation; exact multi-page CSV; filter/back navigation; desktop and mobile mutations; quantity/history refresh; network, GraphQL and malformed-response recovery; duplicate-submit protection; and axe accessibility scans.")
            except Exception:
                log.flush()
                print((temporary / "server.log").read_text(encoding="utf-8"), file=sys.stderr)
                raise
            finally:
                if os.name == "nt" and server.poll() is None:
                    # Windows venv Python may launch a child interpreter. Stop
                    # our entire process tree before deleting its temporary DB.
                    subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                elif server.poll() is None:
                    server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
