"""Bounded, lease-aware engine cache. No database/driver imports are needed here.

A busy entry is never evicted. When every entry is busy we wait for a bounded
interval instead of allocating another pool. Keys represent credentials, not URLs.
"""
from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class DisposableEngine(Protocol):
    async def dispose(self, close: bool = True) -> None: ...


E = TypeVar("E", bound=DisposableEngine)


class DatabaseCapacityError(TimeoutError):
    """The process connection budget is busy; do not allocate another engine."""


@dataclass
class Entry(Generic[E]):
    engine: E
    last_used: float
    leases: int = 0
    invalidated: bool = False


class BoundedEngineRegistry(Generic[E]):
    def __init__(
        self, *, maximum: int, ttl: float, wait_timeout: float,
        is_busy: Callable[[E], bool] | None = None,
    ) -> None:
        if maximum < 1 or ttl <= 0 or wait_timeout <= 0:
            raise ValueError("Engine cache limits must be positive")
        self.maximum = maximum
        self.ttl = ttl
        self.wait_timeout = wait_timeout
        self.entries: OrderedDict[str, Entry[E]] = OrderedDict()
        self._condition = asyncio.Condition()
        self._is_busy = is_busy or (lambda _: False)
        self._metrics = {"hits": 0, "misses": 0, "evictions": 0, "rejected": 0}

    def _busy(self, entry: Entry[E]) -> bool:
        return entry.leases > 0 or self._is_busy(entry.engine)

    async def _remove_locked(self, key: str) -> None:
        entry = self.entries[key]
        # Dispose before admitting a replacement, so physical pools cannot overlap.
        await entry.engine.dispose()
        self.entries.pop(key, None)
        self._metrics["evictions"] += 1

    async def _prune_locked(self) -> None:
        now = time.monotonic()
        for key, entry in list(self.entries.items()):
            if not self._busy(entry) and (entry.invalidated or now - entry.last_used >= self.ttl):
                await self._remove_locked(key)

    async def prune(self) -> None:
        async with self._condition:
            await self._prune_locked()
            self._condition.notify_all()

    async def _obtain(self, key: str, factory: Callable[[], E], *, lease: bool) -> Entry[E]:
        deadline = time.monotonic() + self.wait_timeout
        async with self._condition:
            while True:
                await self._prune_locked()
                entry = self.entries.get(key)
                if entry is not None and not entry.invalidated:
                    entry.last_used = time.monotonic()
                    entry.leases += int(lease)
                    self.entries.move_to_end(key)
                    self._metrics["hits"] += 1
                    return entry
                if entry is None:
                    if len(self.entries) >= self.maximum:
                        victim = next(
                            (k for k, v in self.entries.items() if not self._busy(v)), None,
                        )
                        if victim is not None:
                            await self._remove_locked(victim)
                    if len(self.entries) < self.maximum:
                        entry = Entry(factory(), time.monotonic(), leases=int(lease))
                        self.entries[key] = entry
                        self._metrics["misses"] += 1
                        return entry
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._metrics["rejected"] += 1
                    raise DatabaseCapacityError("Tenant database capacity temporarily busy")
                try:
                    # Poll also covers compatibility callers using an engine directly.
                    await asyncio.wait_for(self._condition.wait(), min(remaining, 0.1))
                except TimeoutError:
                    pass

    async def get(self, key: str, factory: Callable[[], E]) -> E:
        """Compatibility lookup; runtime sessions must use lease()."""
        return (await self._obtain(key, factory, lease=False)).engine

    @asynccontextmanager
    async def lease(self, key: str, factory: Callable[[], E]) -> AsyncIterator[E]:
        entry = await self._obtain(key, factory, lease=True)
        try:
            yield entry.engine
        finally:
            async with self._condition:
                entry.leases -= 1
                entry.last_used = time.monotonic()
                if entry.invalidated and not self._busy(entry) and self.entries.get(key) is entry:
                    await self._remove_locked(key)
                self._condition.notify_all()

    async def invalidate(self, key: str) -> None:
        async with self._condition:
            entry = self.entries.get(key)
            if entry is not None:
                entry.invalidated = True
                if not self._busy(entry):
                    await self._remove_locked(key)
            self._condition.notify_all()

    async def close(self) -> None:
        async with self._condition:
            for key in list(self.entries):
                entry = self.entries[key]
                entry.invalidated = True
                # Active sessions close on their normal exit; never dispose under them.
                if not self._busy(entry):
                    await self._remove_locked(key)
            self._condition.notify_all()

    def metrics(self) -> dict[str, int]:
        return {
            **self._metrics, "size": len(self.entries), "limit": self.maximum,
            "leased": sum(e.leases for e in self.entries.values()),
        }
