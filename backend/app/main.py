import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from strawberry.fastapi import GraphQLRouter

from app.config import ALLOWED_ORIGINS, DATABASE_PATH, FRONTEND_DIST
from app.database import Database
from app.graphql.schema import schema


def create_app(database_path: Path | None = None, frontend_dist: Path | None = None):
    database = Database(database_path or DATABASE_PATH)
    dist = Path(frontend_dist or FRONTEND_DIST).resolve()

    @asynccontextmanager
    async def lifespan(app):
        try:
            await run_in_threadpool(database.check_schema)
            yield
        finally:
            database.dispose()

    app = FastAPI(title="Small Shop Inventory", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.database = database
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def protect_local_api(request: Request, call_next):
        if request.url.path.rstrip("/") == "/graphql" and request.method == "POST":
            origin = request.headers.get("origin")
            same_origin = str(request.base_url).rstrip("/")
            if (origin and origin not in ALLOWED_ORIGINS and origin != same_origin) or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": "Origin is not allowed."}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                return JSONResponse({"error": "Use application/json."}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/graphql"):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def context(request: Request):
        return {"database": request.app.state.database}

    app.include_router(GraphQLRouter(
        schema, context_getter=context, allow_queries_via_get=False,
        graphql_ide="graphiql" if os.environ.get("INVENTORY_GRAPHIQL") == "1" else None,
    ), prefix="/graphql")

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        parts = path.strip("/").split("/")
        is_page = path in {"", "products", "products/new", "history"} or (
            len(parts) in {2, 3} and parts[0] == "products" and parts[1].isdigit()
            and (len(parts) == 2 or parts[2] == "edit")
        )
        if not is_page:
            raise HTTPException(status_code=404, detail="Not found")
        if not (dist / "index.html").is_file():
            return HTMLResponse("<h1>Frontend not built</h1><p>From frontend, run npm install and npm run build, then restart the backend. During development use http://localhost:5173.</p>", status_code=503)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
