import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = Path(os.environ.get("INVENTORY_DATABASE", ROOT / "data/inventory.sqlite3")).resolve()
FRONTEND_DIST = ROOT / "frontend/dist"
SCHEMA_VERSION = "0001"

# No wildcard CORS: the Vite proxy and the built UI use the same origin.
ALLOWED_ORIGINS = {
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:8000", "http://127.0.0.1:8000",
}
