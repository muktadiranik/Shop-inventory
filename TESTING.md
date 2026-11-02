# Verification report

## Results

- **104 backend tests passed**, including HTTP/GraphQL integration tests and repeatable data-seeding tests against real migrated temporary SQLite databases.
- **26 frontend utility tests passed**.
- **Vite production build passed**.
- **Chromium browser workflow passed** against the production build, using an automatically started/stopped server and a separate temporary database.
- **axe-core WCAG A/AA scans passed** on the checked desktop/mobile pages.

No shop data is used as test fixtures or modified by the tests.

## Regressions found and fixed

1. **Back navigation could lose the requested inventory page.** The query hook briefly exposed the preceding filter's data before its effect ran. A previous count of one could redirect a valid page-two URL to page one. `frontend/src/hooks/useQuery.js` now associates results with their query, variables, and refresh version, and does not expose obsolete results. The browser test reproduces filtering a 25-product inventory down to one result and returning to page two.
2. **Malformed API responses could expose JavaScript errors or be mistaken for mutation success.** `frontend/src/api/client.js` now validates GraphQL envelopes and mutation payloads and returns useful request errors. Tests cover JSON `null`, arrays, malformed errors, invalid data shapes, missing success data, and cancellation while reading response bodies.
3. **A populated inventory table could overflow the mobile document.** A visually hidden, absolutely positioned caption was not contained by its scrolling region. `frontend/src/styles/app.css` now establishes a positioned table wrapper. Browser checks verify that only the table scrolls horizontally, not the whole document.

## Coverage added

`backend/tests/test_graphql_inventory.py` covers:

- Product creation, metadata editing, archive restrictions, and archived read-only behavior.
- Normalized duplicate SKUs, including archived and concurrently created products.
- Invalid business inputs and GraphQL input types; invalid edits leave metadata unchanged.
- Opening stock (including zero), receipts, issues, positive/negative adjustments, and required reasons.
- Insufficient stock and six concurrent HTTP issues competing for limited stock.
- Full snapshot preservation after rejected operations and rollback after forced database insert failures; the database remains usable afterward.
- Integer minor-unit price storage, exact GraphQL round trips, exact decimal CSV values, and aggregate quantities exceeding GraphQL Int range.
- Exact preserved movement history, inclusive UTC date boundaries, stable ordering, pagination, search, category/low-stock/archive filters, and dashboard totals.
- Filtered CSV exports containing every matching row beyond the page size, with exact names, categories, prices, balances, and statuses.

Service tests also check concurrent archive/receipt behavior so remaining stock cannot be hidden by an archive race.

`backend/tests/test_seed.py` verifies the 120-product/760-movement catalog, chronological nonnegative stock histories, recent chilled-item dates, archived/low-stock states, deterministic generation, repeatability without overwriting operator edits, preservation of existing SKU collisions, whole-batch rollback, and consistent pre-seed backups.

`backend/browser_smoke.py` verifies:

- Real API validation errors in alerts and associated accessible form fields.
- Network and GraphQL failures on both reads and mutations, preserved form input, and successful explicit retries.
- Automatic balance and history refresh after successful stock mutations.
- Duplicate-submit protection and archive/history preservation.
- Correctly quoted CSV downloads with all 22 filtered rows when the UI page size is 20.
- Product forms, lists, detail/history pages, dashboard totals, and horizontal-scroll containment at 1440px and 390px widths.
- Back navigation after filtering, deep-link refresh, malformed-response recovery, no uncaught browser exceptions, and automated accessibility scans.

## Reproduce (PowerShell, project root)

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests -q
npm --prefix .\frontend test
npm --prefix .\frontend run build
.\.venv\Scripts\python.exe .\backend\browser_smoke.py
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini check
```

The browser check requires the optional `browser` extra and Chromium; see README setup instructions.

## Not verified / remaining limitations

- Browser execution used Chromium with desktop and mobile viewport sizes, not Firefox, Safari/WebKit, or physical mobile devices.
- Automated accessibility checks do not verify actual screen-reader behavior or replace a manual accessibility audit.
- Forced database errors and concurrent requests were tested, but not operating-system crashes, disk-full conditions, or power loss.
- The backend test run emits one upstream Starlette warning that its `httpx` TestClient compatibility is deprecated. Tests pass; this does not affect the application server. No dependency migration was required for these application fixes.
