#!/usr/bin/env python3
"""Backup lógico de TODAS as bases e roles; não altera a stack nem o banco.

Não inclui objetos S3/MinIO, certificados, .env ou filas. Os arquivos contêm
informação confidencial (inclusive hashes de roles). Armazene fora da VPS,
criptografado, e teste restauração em ambiente separado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose', required=True, type=Path)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--service', default='scheduler-postgres')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=3600)
    args = parser.parse_args()
    if args.timeout < 1 or not args.compose.is_file():
        parser.error('Informe Compose existente e timeout positivo')
    compose = ['docker','compose','-f',str(args.compose.resolve())]
    if args.env_file:
        if not args.env_file.is_file():
            parser.error('Arquivo de ambiente não encontrado')
        compose += ['--env-file',str(args.env_file.resolve())]
    base=compose+['exec','-T',args.service,'sh','-eu','-c']
    os.umask(0o077)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
    args.output.mkdir(parents=True,exist_ok=True)
    work=args.output/('.incomplete-'+stamp)
    work.mkdir(mode=0o700)
    authentication='export PGPASSWORD="$POSTGRES_PASSWORD"; '
    def execute(script: str, *values: str, stdout: object = subprocess.PIPE, stdin: object = None) -> subprocess.CompletedProcess:
        return subprocess.run(base+[authentication+script,'backup',*values],
                              stdout=stdout,stdin=stdin,stderr=subprocess.PIPE,check=True,timeout=args.timeout)
    try:
        query="SELECT coalesce(json_agg(datname ORDER BY datname),'[]'::json) FROM pg_database WHERE datallowconn AND NOT datistemplate;"
        result=execute('psql --no-password -X -v ON_ERROR_STOP=1 -qAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"',query)
        databases=json.loads(result.stdout)
        if not databases or not all(isinstance(name,str) for name in databases):
            raise ValueError('Lista de bases inválida ou vazia')
        globals_file=work/'globals.sql'
        with globals_file.open('wb') as output:
            execute('pg_dumpall --no-password --globals-only -U "$POSTGRES_USER"',stdout=output)
        files=[]
        for number,database in enumerate(databases,1):
            slug=re.sub(r'[^a-zA-Z0-9_.-]','_',database)[:60]
            dump=work/f'{number:04d}-{slug}.dump'
            with dump.open('wb') as output:
                execute('pg_dump --format=custom --create --no-password -U "$POSTGRES_USER" -d "$1"',database,stdout=output)
            # Parse the archive catalog; this is NOT a successful restore test.
            with dump.open('rb') as archive:
                execute('pg_restore --list >/dev/null',stdin=archive)
            files.append({'database':database,'file':dump.name,'bytes':dump.stat().st_size})
            print(f'Arquivo {number}/{len(databases)} criado; catálogo legível.',flush=True)
        checksums=[]
        for file in sorted(work.iterdir()):
            with file.open('rb') as source:
                digest=hashlib.file_digest(source,'sha256').hexdigest()
            checksums.append(f'{digest}  {file.name}')
        (work/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n')
        manifest={'created_at_utc':stamp,'type':'postgres-logical-per-database',
                  'cross_database_atomic_snapshot':False,'restoration_tested':False,
                  'includes_s3_objects':False,'databases':files,'globals':'globals.sql'}
        (work/'MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
        final=args.output/('postgres-'+stamp)
        work.rename(final)
        print(f'Backup concluído: {final.resolve()}')
        print('Copie de forma criptografada para outro servidor e homologue uma restauração completa.')
        return 0
    except (subprocess.SubprocessError,ValueError,OSError):
        # stderr can contain database details: do not print it automatically.
        print(f'BACKUP NÃO CONCLUÍDO. Arquivos parciais preservados em {work.resolve()}.')
        print('Nenhum arquivo parcial deve ser tratado como backup válido.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
