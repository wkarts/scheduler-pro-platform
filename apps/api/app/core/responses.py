from typing import Any


def success(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data if data is not None else {}, "meta": meta or {}}
