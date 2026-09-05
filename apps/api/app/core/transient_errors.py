"""Classify only capacity/connectivity faults, never credentials or SQL defects."""
from app.db.engine_registry import DatabaseCapacityError

TRANSIENT_SQLSTATES = {"53300", "57P01", "57P02", "57P03"}


def is_transient_database_error(exc: BaseException) -> bool:
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        if isinstance(error, DatabaseCapacityError):
            return True
        state = str(getattr(error, "sqlstate", "") or getattr(error, "pgcode", ""))
        if state in TRANSIENT_SQLSTATES or state.startswith("08"):
            return True
        module = type(error).__module__
        if module.startswith("sqlalchemy"):
            if type(error).__name__ == "TimeoutError" or getattr(error, "connection_invalidated", False):
                return True
        for child in (getattr(error, "orig", None), error.__cause__, error.__context__):
            if isinstance(child, BaseException):
                pending.append(child)
    return False
