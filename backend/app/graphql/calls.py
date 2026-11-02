import logging

from graphql import GraphQLError
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from app.errors import InventoryError

logger = logging.getLogger(__name__)


async def call(info, function, *args, **kwargs):
    try:
        return await run_in_threadpool(function, info.context["database"], *args, **kwargs)
    except InventoryError:
        raise
    except OperationalError as exc:
        if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
            raise InventoryError("DATABASE_BUSY", "Inventory is busy. Please refresh and try again.") from exc
        logger.exception("Database operation failed")
        raise GraphQLError("An internal error occurred.", extensions={"code": "INTERNAL_ERROR"}) from exc
    except Exception as exc:
        logger.exception("Inventory operation failed")
        raise GraphQLError("An internal error occurred.", extensions={"code": "INTERNAL_ERROR"}) from exc


async def query_call(info, function, *args, **kwargs):
    try:
        return await call(info, function, *args, **kwargs)
    except InventoryError as exc:
        raise GraphQLError(exc.message, extensions={"code": exc.code, "field": exc.field}) from exc
