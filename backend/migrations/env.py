from alembic import context

from app.config import DATABASE_PATH
from app.database import Database
from app.models import Base

config = context.config
database = Database(config.attributes.get("database_path", DATABASE_PATH))

with database.engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

database.dispose()
