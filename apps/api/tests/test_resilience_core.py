"""Executable without services: python -m unittest discover -s tests -p test_resilience_core.py -v.

FakeEngine is a deterministic pool-lifecycle double, NOT a PostgreSQL integration test.
"""
import ast
import asyncio
import time
import unittest
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.core.background_tasks import BoundedTaskRunner
from app.core.config import Settings
from app.core.transient_errors import is_transient_database_error
from app.db.connection_budget import capacity_snapshot
from app.db.engine_registry import BoundedEngineRegistry, DatabaseCapacityError


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = 0
        self.busy = False

    async def dispose(self, close: bool = True) -> None:
        self.disposed += 1


class EngineRegistryTests(unittest.IsolatedAsyncioTestCase):
    def registry(self, maximum: int = 2, ttl: float = 30) -> BoundedEngineRegistry[FakeEngine]:
        return BoundedEngineRegistry(maximum=maximum, ttl=ttl, wait_timeout=0.025, is_busy=lambda e:e.busy)

    async def test_reuses_same_key(self) -> None:
        registry = self.registry()
        async with registry.lease('a', FakeEngine) as first:
            async with registry.lease('a', FakeEngine) as second:
                self.assertIs(first, second)
                self.assertEqual(registry.metrics()['leased'], 2)
        self.assertEqual(registry.metrics()['leased'], 0)
        await registry.close()
        self.assertEqual(first.disposed, 1)

    async def test_busy_entry_is_not_evicted_at_capacity(self) -> None:
        registry = self.registry(maximum=1)
        async with registry.lease('a', FakeEngine) as first:
            with self.assertRaises(DatabaseCapacityError):
                async with registry.lease('b', FakeEngine):
                    self.fail('Busy cache exceeded its configured limit')
            self.assertEqual(first.disposed, 0)
            self.assertEqual(registry.metrics()['size'], 1)
        await registry.close()

    async def test_waiter_resumes_after_release(self) -> None:
        registry = self.registry(maximum=1)
        started = asyncio.Event()
        async def waiter() -> None:
            started.set()
            async with registry.lease('b', FakeEngine):
                self.assertEqual(registry.metrics()['size'], 1)
        async with registry.lease('a', FakeEngine) as first:
            task = asyncio.create_task(waiter())
            await started.wait()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
        await task
        self.assertEqual(first.disposed, 1)
        await registry.close()

    async def test_idle_lru_entry_is_evicted(self) -> None:
        registry = self.registry()
        first = await registry.get('a', FakeEngine)
        second = await registry.get('b', FakeEngine)
        await registry.get('a', FakeEngine)
        await registry.get('c', FakeEngine)
        self.assertEqual(second.disposed, 1)
        self.assertEqual(first.disposed, 0)
        await registry.close()

    async def test_active_ttl_entry_survives_prune(self) -> None:
        registry = self.registry(ttl=0.001)
        async with registry.lease('a', FakeEngine) as first:
            registry.entries['a'].last_used = time.monotonic()-10
            await registry.prune()
            self.assertEqual(first.disposed, 0)
        registry.entries['a'].last_used = time.monotonic()-10
        await registry.prune()
        self.assertEqual(first.disposed, 1)

    async def test_invalidation_defers_disposal_until_release(self) -> None:
        registry = self.registry()
        async with registry.lease('a', FakeEngine) as first:
            await registry.invalidate('a')
            self.assertEqual(first.disposed, 0)
            with self.assertRaises(DatabaseCapacityError):
                async with registry.lease('a', FakeEngine):
                    self.fail('An invalidated credential was reused')
        self.assertEqual(first.disposed, 1)
        async with registry.lease('a', FakeEngine) as replacement:
            self.assertIsNot(first, replacement)
        await registry.close()

    async def test_cancelled_lease_is_released(self) -> None:
        registry = self.registry(maximum=1)
        started = asyncio.Event()
        async def task_body() -> None:
            async with registry.lease('a', FakeEngine):
                started.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(task_body())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(registry.metrics()['leased'], 0)
        async with registry.lease('b', FakeEngine):
            pass
        await registry.close()

    async def test_cancelled_waiter_does_not_leak_capacity(self) -> None:
        registry = self.registry(maximum=1)
        async with registry.lease('a', FakeEngine):
            task = asyncio.create_task(registry.get('b', FakeEngine))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(registry.metrics()['leased'], 0)
        await registry.close()

    async def test_exception_inside_session_releases_lease(self) -> None:
        registry = self.registry()
        with self.assertRaises(ValueError):
            async with registry.lease('a', FakeEngine):
                raise ValueError('business operation failed')
        self.assertEqual(registry.metrics()['leased'], 0)
        await registry.close()

    async def test_close_defers_busy_entry(self) -> None:
        registry = self.registry()
        async with registry.lease('a', FakeEngine) as engine:
            await registry.close()
            self.assertEqual(engine.disposed, 0)
        self.assertEqual(engine.disposed, 1)
        self.assertEqual(registry.metrics()['size'], 0)

    async def test_compatibility_lookup_honors_checked_out_pool(self) -> None:
        registry = self.registry(maximum=1)
        engine=await registry.get('a',FakeEngine)
        engine.busy=True
        with self.assertRaises(DatabaseCapacityError):
            await registry.get('b',FakeEngine)
        engine.busy=False
        await registry.close()

    async def test_factory_error_does_not_consume_entry(self) -> None:
        registry = self.registry()
        def failing() -> FakeEngine:
            raise ValueError('configuration')
        with self.assertRaises(ValueError):
            await registry.get('a',failing)
        self.assertEqual(registry.metrics()['size'],0)
        await registry.close()

    async def test_many_tenants_never_exceed_pool_limit(self) -> None:
        registry=self.registry(maximum=4)
        peak=0
        for index in range(200):
            async with registry.lease(str(index),FakeEngine):
                peak=max(peak,registry.metrics()['size'])
        self.assertEqual(peak,4)
        self.assertEqual(registry.metrics()['evictions'],196)
        await registry.close()

    async def test_concurrent_same_tenant_builds_only_one_engine(self) -> None:
        registry=self.registry()
        created=0
        def factory() -> FakeEngine:
            nonlocal created
            created+=1
            return FakeEngine()
        async def use() -> None:
            async with registry.lease('shared',factory):
                await asyncio.sleep(0.001)
        await asyncio.gather(*(use() for _ in range(100)))
        self.assertEqual(created,1)
        self.assertEqual(registry.metrics()['leased'],0)
        await registry.close()


class BackgroundTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_has_hard_limit(self) -> None:
        runner=BoundedTaskRunner(maximum=3,concurrency=1,timeout=5)
        gate=asyncio.Event()
        self.assertTrue(runner.submit(gate.wait))
        self.assertTrue(runner.submit(gate.wait))
        self.assertTrue(runner.submit(gate.wait))
        self.assertFalse(runner.submit(gate.wait))
        self.assertEqual(runner.metrics()['pending'],3)
        gate.set()
        await runner.close()
        self.assertEqual(runner.metrics()['completed'],3)

    async def test_concurrency_is_bounded(self) -> None:
        runner=BoundedTaskRunner(maximum=20,concurrency=2,timeout=2)
        active=0
        peak=0
        async def work() -> None:
            nonlocal active,peak
            active+=1
            peak=max(peak,active)
            await asyncio.sleep(0.002)
            active-=1
        for _ in range(20):
            runner.submit(work)
        await runner.close()
        self.assertEqual(peak,2)
        self.assertEqual(runner.metrics()['completed'],20)

    async def test_task_timeout_and_cancellation(self) -> None:
        runner=BoundedTaskRunner(maximum=2,concurrency=1,timeout=0.005)
        cleaned=asyncio.Event()
        async def work() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        runner.submit(work)
        await runner.close()
        self.assertTrue(cleaned.is_set())
        self.assertEqual(runner.metrics()['timed_out'],1)

    async def test_exception_is_observed_without_crashing_request(self) -> None:
        runner=BoundedTaskRunner(maximum=2,concurrency=1,timeout=1)
        async def failing() -> None:
            raise RuntimeError('storage down')
        runner.submit(failing)
        await runner.close()
        self.assertEqual(runner.metrics()['failed'],1)

    async def test_shutdown_rejects_new_work(self) -> None:
        runner=BoundedTaskRunner(maximum=1,concurrency=1,timeout=1)
        await runner.close()
        self.assertFalse(runner.submit(asyncio.Event().wait))

    async def test_forced_shutdown_cleans_tasks(self) -> None:
        runner=BoundedTaskRunner(maximum=1,concurrency=1,timeout=10)
        runner.submit(asyncio.Event().wait)
        await asyncio.sleep(0)
        await runner.close(grace=0)
        self.assertEqual(runner.metrics()['pending'],0)


class BudgetAndErrorTests(unittest.TestCase):
    def test_default_api_budget(self) -> None:
        config=Settings(_env_file=None)
        total=config.db_platform_pool_size+config.db_platform_max_overflow+config.tenant_engine_cache_max*(config.db_tenant_pool_size+config.db_tenant_max_overflow)
        self.assertEqual(total,22)
        self.assertLessEqual(total,config.db_connection_budget_per_process)

    def test_worker_budget(self) -> None:
        config=Settings(_env_file=None,db_platform_pool_size=1,db_platform_max_overflow=0,
                        db_tenant_pool_size=1,db_tenant_max_overflow=0,
                        tenant_engine_cache_max=4,db_connection_budget_per_process=8)
        self.assertEqual(config.db_platform_pool_size+config.tenant_engine_cache_max*config.db_tenant_pool_size,5)

    def test_unbounded_pool_values_are_rejected(self) -> None:
        for options in ({'db_platform_pool_size':0},{'db_tenant_pool_size':0},
                        {'db_platform_max_overflow':-1},{'db_tenant_max_overflow':-1},
                        {'tenant_engine_cache_max':0},{'tenant_engine_cache_max':64}):
            with self.subTest(options=options),self.assertRaises(ValidationError):
                Settings(_env_file=None,**options)

    def test_invalid_thresholds_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None,db_capacity_warning_percent=95,db_capacity_critical_percent=90)

    def test_idle_is_not_confused_with_idle_transaction(self) -> None:
        row={'maximum':100,'reserved':0,'superuser_reserved':3,'used':50,'active':5,'idle':45,'idle_in_transaction':0}
        data=capacity_snapshot(row)
        self.assertEqual(data['ordinary_limit'],97)
        self.assertEqual(data['free_ordinary_slots'],47)
        self.assertEqual(data['reserved_slots'],3)
        self.assertEqual(data['status'],'ok')

    def test_capacity_counts_real_reservations(self) -> None:
        row={'maximum':100,'reserved':5,'superuser_reserved':3,'used':90,'active':5,'idle':85,'idle_in_transaction':0}
        data=capacity_snapshot(row)
        self.assertEqual(data['status'],'critical')
        self.assertEqual(data['ordinary_limit'],92)

    def test_transient_errors_recognize_wrapped_sqlstate(self) -> None:
        class DatabaseError(Exception):
            sqlstate='53300'
        root=RuntimeError('wrapped')
        root.__cause__=DatabaseError()
        self.assertTrue(is_transient_database_error(root))
        self.assertTrue(is_transient_database_error(SQLAlchemyTimeoutError()))
        self.assertTrue(is_transient_database_error(DatabaseCapacityError()))

    def test_invalid_sql_and_invalid_password_are_not_transient(self) -> None:
        class QueryError(Exception):
            sqlstate='42601'
        class PasswordError(Exception):
            sqlstate='28P01'
        self.assertFalse(is_transient_database_error(QueryError()))
        self.assertFalse(is_transient_database_error(PasswordError()))
        self.assertFalse(is_transient_database_error(ValueError()))

    def test_exception_cause_cycle_does_not_hang(self) -> None:
        exc=ValueError()
        exc.__cause__=exc
        self.assertFalse(is_transient_database_error(exc))

    def test_async_session_iterators_are_explicitly_closed(self) -> None:
        root=Path(__file__).resolve().parents[1]/'app'
        checked=0
        for path in root.rglob('*.py'):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node,ast.AsyncFor):
                    continue
                if isinstance(node.iter,ast.Call) and isinstance(node.iter.func,ast.Name):
                    self.assertNotIn(node.iter.func.id,{'platform_session','tenant_session'},str(path))
                if isinstance(node.iter,ast.Name) and node.iter.id.startswith('_session_scope_'):
                    owners=[n for n in ast.walk(tree) if isinstance(n,ast.AsyncWith) and any(
                        isinstance(i.optional_vars,ast.Name) and i.optional_vars.id==node.iter.id for i in n.items)]
                    self.assertEqual(len(owners),1)
                    self.assertIsInstance(owners[0].items[0].context_expr,ast.Call)
                    self.assertEqual(owners[0].items[0].context_expr.func.id,'aclosing')
                    checked+=1
        self.assertEqual(checked,40)

    def test_report_tasks_use_shared_worker_runtime(self) -> None:
        root=Path(__file__).resolve().parents[1]/'app'
        source=(root/'workers/agenda_report_tasks.py').read_text()
        self.assertIn('from app.workers.tasks import _run',source)
        self.assertNotIn('new_event_loop',source)

    def test_db_cache_identity_excludes_hostname(self) -> None:
        root=Path(__file__).resolve().parents[1]/'app'
        source=(root/'db/session.py').read_text()
        tree=ast.parse(source)
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_tenant_cache_key')
        snippet=ast.get_source_segment(source,method)
        self.assertNotIn('context.hostname',snippet)
        for key in ('tenant_id','database_user','database_password_ref','database_credential_version'):
            self.assertIn(f'context.{key}',snippet)


if __name__=='__main__':
    unittest.main()
