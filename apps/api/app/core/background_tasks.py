"""Bounded best-effort tasks; business events must use the transactional outbox."""
import asyncio
from collections.abc import Awaitable, Callable


class BoundedTaskRunner:
    def __init__(self, *, maximum: int, concurrency: int, timeout: float) -> None:
        if maximum < 1 or concurrency < 1 or concurrency > maximum or timeout <= 0:
            raise ValueError("Invalid background-task limits")
        self.maximum = maximum
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self.tasks: set[asyncio.Task[None]] = set()
        self._closing = False
        self._counts = {"accepted": 0, "dropped": 0, "completed": 0, "failed": 0, "timed_out": 0}

    def submit(self, factory: Callable[[], Awaitable[None]]) -> bool:
        if self._closing or len(self.tasks) >= self.maximum:
            self._counts["dropped"] += 1
            return False
        task = asyncio.create_task(self._execute(factory))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        self._counts["accepted"] += 1
        return True

    async def _execute(self, factory: Callable[[], Awaitable[None]]) -> None:
        try:
            # Include queue wait in the deadline; never drain a stale logging backlog.
            async with asyncio.timeout(self.timeout):
                async with self._semaphore:
                    await factory()
            self._counts["completed"] += 1
        except TimeoutError:
            self._counts["timed_out"] += 1
        except Exception:
            self._counts["failed"] += 1

    async def close(self, *, grace: float = 5.0) -> None:
        self._closing = True
        if not self.tasks:
            return
        _, pending = await asyncio.wait(list(self.tasks), timeout=max(grace, 0))
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def metrics(self) -> dict[str, int]:
        return {**self._counts, "pending": len(self.tasks), "limit": self.maximum}
