from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import SCHEMA_VERSION
from app.errors import InventoryError


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path.as_posix()}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )

        @event.listens_for(self.engine, "connect")
        def configure_connection(connection, _):
            # SQLAlchemy controls BEGIN, including SELECT transactions.
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            # Acquire the write reservation BEFORE checking stock, not on INSERT.
            immediate = connection.get_execution_options().get("inventory_write", False)
            connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    @contextmanager
    def read(self):
        with Session(self.engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def write(self):
        try:
            with Session(self.engine, expire_on_commit=False) as session:
                with session.begin():
                    session.connection(execution_options={"inventory_write": True})
                    yield session
                    session.flush()
        except IntegrityError as exc:
            if "products.sku" in str(exc.orig):
                raise InventoryError("DUPLICATE_SKU", "This SKU is already in use, including archived products.", "sku") from exc
            raise InventoryError("INVALID_INPUT", "The change violates an inventory constraint.") from exc
        except OperationalError as exc:
            if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
                raise InventoryError("DATABASE_BUSY", "Inventory is busy. Check the latest balance before trying again.") from exc
            raise

    def check_schema(self):
        try:
            with self.engine.connect() as connection:
                version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if version != SCHEMA_VERSION:
                raise RuntimeError("Database schema is out of date.")
        except Exception as exc:
            raise RuntimeError("Database is not ready. From backend, run: python -m alembic upgrade head") from exc

    def dispose(self):
        self.engine.dispose()
