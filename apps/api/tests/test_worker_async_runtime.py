import asyncio
from pathlib import Path

from app.workers import tasks


def test_celery_worker_reuses_one_event_loop_across_tasks() -> None:
    seen: list[int] = []

    async def capture_loop() -> int:
        loop_id = id(asyncio.get_running_loop())
        seen.append(loop_id)
        await asyncio.sleep(0)
        return loop_id

    try:
        first = tasks._run(capture_loop())
        second = tasks._run(capture_loop())

        assert first == second
        assert seen == [first, first]
        assert tasks._worker_loop is not None
        assert not tasks._worker_loop.is_closed()
    finally:
        tasks._shutdown_worker_async_runtime()

    assert tasks._worker_loop is None
    assert tasks._worker_loop_pid is None


def test_worker_tasks_do_not_create_a_fresh_loop_per_task() -> None:
    assert tasks.__file__ is not None
    source = Path(tasks.__file__).read_text(encoding="utf-8")

    assert "asyncio.run(" not in source
    assert "loop.run_until_complete(coro)" in source
    assert "worker_process_shutdown.connect" in source
