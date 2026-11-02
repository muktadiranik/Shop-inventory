from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.services.products import create_product

BACKEND = Path(__file__).resolve().parents[1]


def migrate(path, revision="head"):
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_path"] = path
    command.upgrade(config, revision)
    return config


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "inventory.sqlite3"
    migrate(path)
    database = Database(path)
    yield database
    database.dispose()


@pytest.fixture
def make_product(database):
    counter = 0

    def create(**updates):
        nonlocal counter
        counter += 1
        values = {"sku": f"SKU-{counter}", "name": "Notebook", "category": "Stationery", "unit_price_minor": 1299, "low_stock_threshold": 3, "opening_quantity": 10}
        values.update(updates)
        return create_product(database, values)["product"]
    return create


@pytest.fixture
def client(database, tmp_path):
    app = create_app(database.path, tmp_path / "unbuilt")
    with TestClient(app) as client:
        yield client
