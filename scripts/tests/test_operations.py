"""Tests of the operation scripts' boundaries. No Docker or real database is used."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BUDGET = ROOT / 'scripts/operations/check-connection-budget.py'
BACKUP = ROOT / 'scripts/operations/backup-postgres.py'


def service(*, worker=False, replicas=1):
    return {
        'environment': {'DB_CONNECTION_BUDGET_PER_PROCESS': 8 if worker else 24,
            'DB_PLATFORM_POOL_SIZE': 1 if worker else 4,
            'DB_PLATFORM_MAX_OVERFLOW': 0 if worker else 2,
            'DB_TENANT_POOL_SIZE': 1, 'DB_TENANT_MAX_OVERFLOW': 0 if worker else 1,
            'TENANT_ENGINE_CACHE_MAX': 4 if worker else 8},
        'command': ['celery','-A','app','worker','--concurrency=2'] if worker else [],
        'deploy': {'replicas': replicas},
    }


class BudgetTests(unittest.TestCase):
    def run_budget(self, services, maximum=100):
        return subprocess.run([sys.executable,str(BUDGET),'--max-connections',str(maximum)],
                              input=json.dumps({'services':services}),text=True,capture_output=True)

    def test_current_default_topology(self):
        result=self.run_budget({'scheduler-api':service(),'scheduler-worker-default':service(worker=True),
                                'scheduler-worker-whatsapp':service(worker=True)})
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual((data['pooled_total'],data['planned_total'],data['ordinary_capacity']),(42,57,97))

    def test_replicas_and_headroom_are_counted(self):
        result=self.run_budget({'scheduler-api':service(replicas=4)})
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['pooled_total'],88)

    def test_unbounded_overflow_is_rejected(self):
        config=service();config['environment']['DB_PLATFORM_MAX_OVERFLOW']=-1
        self.assertEqual(self.run_budget({'scheduler-api':config}).returncode,2)

    def test_old_cache_setting_is_rejected(self):
        config=service();config['environment']['TENANT_ENGINE_CACHE_MAX']=64
        self.assertEqual(self.run_budget({'scheduler-api':config}).returncode,2)

    def test_worker_concurrency_must_be_explicit(self):
        config=service(worker=True);config['command'].pop()
        self.assertEqual(self.run_budget({'scheduler-worker-default':config}).returncode,2)

    def test_no_secret_is_echoed(self):
        config=service();config['environment']['PASSWORD']='DO_NOT_ECHO_THIS_SECRET'
        result=self.run_budget({'scheduler-api':config})
        self.assertNotIn('DO_NOT_ECHO_THIS_SECRET',result.stdout+result.stderr)


class BackupTests(unittest.TestCase):
    def load_script(self):
        spec=importlib.util.spec_from_file_location('backup_operations',BACKUP)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_backup_manifest_and_atomic_completion_without_claiming_restore(self):
        module=self.load_script()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);compose=root/'compose.yaml';compose.write_text('services: {}\n')
            destination=root/'backups';calls=[]
            database='tenant; echo BAD'  # Must remain ONE positional argument; never interpolate it into shell code.
            def fake_run(args,**kwargs):
                calls.append(args)
                if 'psql ' in args[-2] or (len(args)>2 and 'psql ' in args[-3]):
                    return subprocess.CompletedProcess(args,0,json.dumps(['platform',database]).encode(),b'')
                output=kwargs.get('stdout')
                if hasattr(output,'write'):
                    output.write(b'fake dump for boundary test, NOT a PostgreSQL archive')
                return subprocess.CompletedProcess(args,0,b'',b'')
            with patch.object(sys,'argv',['backup','--compose',str(compose),'--output',str(destination)]), \
                 patch.object(module.subprocess,'run',side_effect=fake_run), \
                 patch.object(module.os,'umask'),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(),0)
            completed=list(destination.glob('postgres-*'));self.assertEqual(len(completed),1)
            manifest=json.loads((completed[0]/'MANIFEST.json').read_text())
            self.assertFalse(manifest['restoration_tested'])
            self.assertFalse(manifest['cross_database_atomic_snapshot'])
            self.assertEqual(len(manifest['databases']),2)
            self.assertFalse(list(destination.glob('.incomplete-*')))
            self.assertTrue((completed[0]/'SHA256SUMS.txt').is_file())
            tenant_dump=next(c for c in calls if c[-1]==database)
            self.assertNotIn(database,tenant_dump[-3])

    def test_failure_never_publishes_a_completed_backup(self):
        module=self.load_script()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);compose=root/'compose.yaml';compose.write_text('services: {}\n')
            destination=root/'backups'
            with patch.object(sys,'argv',['backup','--compose',str(compose),'--output',str(destination)]), \
                 patch.object(module.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['docker'])), \
                 patch.object(module.os,'umask'),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(),1)
            self.assertFalse(list(destination.glob('postgres-*')))
            self.assertEqual(len(list(destination.glob('.incomplete-*'))),1)


if __name__=='__main__':
    unittest.main()
