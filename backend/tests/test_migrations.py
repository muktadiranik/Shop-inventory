from alembic import command
from sqlalchemy import inspect

from app.database import Database
from app.services import products
from conftest import migrate


def test_migration_reapplication_preserves_data(database, make_product):
    product = make_product()
    migrate(database.path)
    database.check_schema()
    assert products.get_product(database, product["id"])["current_stock"] == 10


def test_migration_round_trip_on_empty_database(tmp_path):
    path = tmp_path / "migration.sqlite3"
    config = migrate(path)
    command.downgrade(config, "base")
    db = Database(path)
    assert "products" not in inspect(db.engine).get_table_names()
    db.dispose()
    command.upgrade(config, "head")
    db = Database(path)
    db.check_schema()
    assert {"products", "stock_movements"} <= set(inspect(db.engine).get_table_names())
    db.dispose()
