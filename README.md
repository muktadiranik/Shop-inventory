# Stockroom — small-shop inventory

A local, single-operator inventory application built with **FastAPI, Strawberry GraphQL, SQLite, React (JavaScript/JSX), Bootstrap 5, and Vite**. All application data operations use `/graphql`; there is no REST inventory API.

## Requirements

- Python **3.12+**
- Node.js **22.12+** (an actively supported Node release is recommended)
- npm

Backend runtime dependencies are pinned in `backend/pyproject.toml`. Frontend dependencies are locked in `frontend/package-lock.json`.

## Start the application (Windows PowerShell)

Run these commands from the project root:

```powershell
Set-Location "D:\Data\Python\Inventory Management System"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[test]"
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
npm --prefix .\frontend ci
npm --prefix .\frontend run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. FastAPI serves both the built React application and `/graphql`. Press **Ctrl+C** to stop.

On a new installation the database starts empty. Add a product through the UI, including its opening quantity, or use the optional sample-data command below. If `.venv` already exists, omit the virtual-environment creation command.

On subsequent runs, only the final server command is needed unless code/dependencies changed. Rebuild the frontend after frontend changes; restart FastAPI after creating the first build.

### Optional realistic sample inventory

From the project root:

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

This adds **120 products across 12 categories** and **760 linked stock movements**, including opening counts, supplier deliveries, retail issues, and physical-count corrections. It includes 114 active products and 6 archived zero-stock products, plus healthy, low-stock, and out-of-stock examples. Nonperishable histories span approximately 60 days; chilled products use a recent six-day window. Prices use the application's existing two-decimal shop currency.

The command is additive and repeatable: existing SKUs, operator edits, and histories are left untouched; rerunning does not add duplicate movements. New data is inserted in one transaction. Before adding rows it creates a consistent SQLite backup in `data/backups/` (or a `backups` folder beside a custom database). It does not delete or reset any records.

Use `-m app.seed --dry-run` to preview the counts without inserting rows. An alternate migrated database can be selected with `--database "C:\absolute\path\inventory.sqlite3"` or the existing `INVENTORY_DATABASE` setting. Refresh the UI after seeding; no frontend rebuild is necessary.

## Local development

Complete dependency installation and migration above, then use two terminals, both starting in the project root.

**Terminal 1 — backend:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\backend --reload --reload-dir .\backend --host 127.0.0.1 --port 8000
```

**Terminal 2 — Vite:**

```powershell
npm --prefix .\frontend run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/graphql` to port 8000, so no CORS configuration or API URL changes are needed. Both development ports are fixed; Vite will report an error rather than silently choose another port.

Optional GraphiQL explorer: set `$env:INVENTORY_GRAPHIQL="1"` before starting the backend, then visit `/graphql` with a browser. It is disabled by default. Application requests always use JSON POST bodies and GraphQL variables.

## Features

- Dashboard with active-product count, total units, and low-stock products.
- Products with unique SKU, name, category, unit price, and low-stock threshold.
- Search by SKU/name, category filters, low-stock filter, archive selector, and pagination.
- Opening stock, stock received, stock issued, and physical-count adjustments.
- Immutable movement history with signed quantity, reason, and UTC timestamp; the UI displays timestamps locally.
- Edit product metadata independently of stock.
- Filtered CSV export of **all** matching inventory rows, independent of the current page.
- Archive zero-stock products while retaining details and all history.
- Responsive layout, labeled forms, keyboard navigation, loading/empty/error states, and duplicate-submit protection.

Not included: sales invoices, multiple warehouses, multiple operators, advanced permissions, remote access, or accounting.

## Inventory rules

- Stock is the sum of the product’s movement ledger. There is no independently stored balance that can drift out of sync.
- Product creation and its opening movement commit together, including a zero opening quantity.
- Receive/issue inputs are positive whole numbers. Issue movements are stored as negative changes.
- An adjustment takes the **actual counted quantity**, not a signed delta, and requires a reason. No-change adjustments are rejected. Receipts and issues also retain a required, editable reason.
- A stock write uses `BEGIN IMMEDIATE` **before reading the current balance**. Validation, movement insertion, and product timestamp updates commit or roll back together. Separate requests, connections, and processes obey the same SQLite write lock; competing issues cannot oversell.
- Database triggers prevent movement edits/deletes. Corrections require another movement.
- SKUs are trimmed, uppercased, immutable after creation, and cannot be reused after archiving. Allowed characters: letters, digits, `.`, `_`, `/`, and `-`, starting with a letter/digit.
- A product is low-stock when `currentStock <= lowStockThreshold`, including zero stock.
- Only products with zero stock may be archived. Archived products are read-only and excluded from active totals; history queries include them.
- Whole-number quantities, thresholds, and minor-unit prices are bounded to `0…2,147,483,647`. Individual movements must also stay in range.

### Prices and currency

Use **one shop currency with two decimal places**. Unit prices are SQLite integer minor units and GraphQL `unitPriceMinor: Int!` everywhere: `29` means `0.29`, `1250` means `12.50`. The UI deliberately does not assume a currency symbol. Price input uses integer/BigInt parsing, not floating-point multiplication. Display formatting does not affect stored values. Maximum price: `21,474,836.47`.

`DashboardSummary.totalUnits` is a decimal digit **String**, avoiding GraphQL’s 32-bit integer limit when summing many products. The UI formats it with BigInt.

## Architecture

```text
backend/app/main.py          FastAPI, local-request protections, frontend serving
backend/app/graphql/         Strawberry types, inputs, queries, and mutations
backend/app/services/        Product rules, transactional stock operations, reporting
backend/app/models.py        SQLAlchemy models and constraints
backend/app/database.py      Per-operation sessions and explicit SQLite transactions
backend/migrations/          Alembic migration history
frontend/src/api/            Shared fetch utility and parameterized GraphQL operations
frontend/src/components/     Reusable forms, tables, pagination, and feedback
frontend/src/pages/          Dashboard, products, add/edit, detail, and global history
data/inventory.sqlite3       Local database (ignored by version control)
```

Strawberry’s official FastAPI integration keeps a single application. Thin async resolvers run complete synchronous service calls in a worker thread; each call creates/closes its own SQLAlchemy session and returns detached data. Sessions are never shared across concurrent resolvers. Reads use a consistent transaction; paginated products load balances in aggregate rather than one query per row.

Frontend state stays in React pages/forms. Navigation uses React Router’s declarative mode. Bootstrap CSS supplies styling; React owns interactive behavior, without Bootstrap DOM-manipulating plugins. No Redux, Apollo, ORM-to-GraphQL generator, or separate export API is needed.

### GraphQL contract

Queries:

- `dashboard`
- `products(filter, limit, offset)` — `search`, `category`, `lowStockOnly`, `archiveStatus`
- `product(id)` — nullable when not found
- `categories(archiveStatus)`
- `stockMovements(filter, limit, offset)` — `productId`, product `search`, `movementType`, `fromDate`, `toDate`
- `inventoryCsv(filter)` — filename, content type, CSV content

Mutations:

- `createProduct(input: CreateProductInput!)`
- `updateProduct(input: UpdateProductInput!)`
- `receiveStock(input: StockInput!)`
- `issueStock(input: StockInput!)`
- `adjustStock(input: AdjustmentInput!)`
- `archiveProduct(id: ID!)`

All mutations return `MutationResult { product, movement, errors { code, field, message } }`. Expected errors such as `DUPLICATE_SKU`, `INSUFFICIENT_STOCK`, `PRODUCT_ARCHIVED`, `NONZERO_STOCK`, `NO_CHANGE`, and `INVALID_INPUT` are structured payload errors. Query validation failures use GraphQL errors with extensions. Unexpected errors are logged server-side and return a sanitized internal error. The fetch utility handles HTTP/network errors and GraphQL errors even with HTTP 200. Stock mutations are **not automatically retried** after uncertain network failures; check history before retrying.

Pagination defaults to 20, with a maximum page size of 100. History sorts by timestamp and ID, newest first. Date filters use inclusive UTC calendar dates. Product search escapes SQL wildcard characters. CSV text fields that could become spreadsheet formulas are prefixed with an apostrophe; a UTF-8 BOM is added by the downloader.

## Checks

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests -q
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini check
.\.venv\Scripts\python.exe -m pip check
npm --prefix .\frontend test
npm --prefix .\frontend run build
```

Backend tests use migrated temporary SQLite files, not the shop database. They cover validation, exact prices, atomic rollback, immutable history, archive behavior, pagination/filters, GraphQL transport, migrations, concurrent connections, and simultaneous HTTP issues. `backend/tests/test_graphql_inventory.py` additionally exercises the complete lifecycle over HTTP, verifies unchanged snapshots after rejected operations and injected database failures, checks date boundaries/stable history pagination, tests concurrent duplicate creation, and compares every field in multi-page CSV exports. Frontend unit tests exercise price/quantity parsing, variables, malformed response handling, and network/GraphQL errors.

### Optional real-browser smoke check

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\backend[browser]"
.\.venv\Scripts\python.exe -m playwright install chromium
npm --prefix .\frontend run build
.\.venv\Scripts\python.exe .\backend\browser_smoke.py
```

The smoke script starts/stops its own server on a free loopback port and uses a temporary database. It exercises create, rapid double submission, receipt, issue validation, adjustments, editing, search/filters, CSV download, archive/history preservation, deep-link refreshes, and recoverable network/GraphQL failures. It verifies active product forms, lists, and detail pages at **1440px and 390px** widths, real API errors and accessible invalid fields, mutation failure/retry behavior, automatic quantity/history refresh, exact filtered CSV exports spanning multiple pages, dashboard totals, and Back navigation after filtering page two. It also runs axe-core WCAG A/AA accessibility scans on the main pages; automated scans complement, but do not replace, manual accessibility testing. axe-core is a development-only dependency and is not bundled into the app.

See [TESTING.md](TESTING.md) for the latest verification results, regression fixes, and limitations.

## Database upgrades and backup

Stop the application and copy `data/inventory.sqlite3` to a safe location before changing schemas. Restore by stopping the application and replacing that file with the backup. CSV is an inventory snapshot, **not** a full backup of movement history.

Create future migrations from the root:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini revision --autogenerate -m "Describe the change"
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
```

Review generated revisions. SQLite batch migrations may rebuild tables; preserve/recreate the movement-protection triggers as necessary. Do not downgrade a live inventory database without a verified backup. The application checks the expected schema version at startup rather than silently creating or replacing tables.

For a different database file, set `$env:INVENTORY_DATABASE="C:\absolute\path\inventory.sqlite3"` before **both** migration and server commands. Keep it on local storage, not a network share. After adding a migration, update `SCHEMA_VERSION` in `backend/app/config.py` to the new head revision.

## Local-only security

Bind to `127.0.0.1`. This version intentionally has no authentication and must not be exposed to a LAN or the internet. It rejects unexpected Host/Origin headers, cross-site API requests, and non-JSON GraphQL POSTs. Production-mode frontend and API share one origin; no wildcard CORS is enabled. Debug mode and GraphiQL are off by default. A shared or remote deployment would require authentication and a separate security review.
