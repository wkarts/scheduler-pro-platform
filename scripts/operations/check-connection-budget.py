#!/usr/bin/env python3
"""Read Docker Compose JSON from stdin, print ONLY pool/capacity metadata.

Example: docker compose config --format json | python3 check-connection-budget.py --max-connections 100
Never save or share the raw Compose JSON: it includes secrets.
"""
import argparse
import json
import shlex
import sys


def positive(value: object, default: int, *, zero: bool = False) -> int:
    result = int(str(value if value is not None else default))
    if result < (0 if zero else 1):
        raise ValueError("Connection/worker limits must be positive (overflow may be zero)")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-connections', required=True, type=int, help='Valor REAL de SHOW max_connections')
    parser.add_argument('--reserved', type=int, default=3, help='Soma das reservas do PostgreSQL; conferir pg_settings')
    parser.add_argument('--operational-margin', type=int, default=15, help='Probes, CLI, migrations e conexões administrativas')
    args = parser.parse_args()
    if args.max_connections <= 0 or args.reserved < 0 or args.operational_margin < 0:
        parser.error('Limites inválidos')
    config = json.load(sys.stdin)
    rows = []
    for name, service in config.get('services', {}).items():
        env = service.get('environment') or {}
        if not isinstance(env, dict) or 'DB_CONNECTION_BUDGET_PER_PROCESS' not in env:
            continue
        command = service.get('command') or []
        if isinstance(command, str):
            command = shlex.split(command)
        is_worker = 'worker' in command and any('celery' in arg for arg in command)
        is_api = name in ('api','scheduler-api')
        if not (is_worker or is_api):
            continue
        processes = positive(env.get('WEB_CONCURRENCY'), 1) if is_api else 1
        for i, arg in enumerate(command):
            flag = '--concurrency' if is_worker else '--workers'
            if arg.startswith(flag+'='):
                processes = positive(arg.split('=',1)[1],1)
            elif arg == flag and i+1 < len(command):
                processes = positive(command[i+1],1)
        if is_worker and not any(a.startswith('--concurrency') for a in command):
            raise ValueError(f'{name}: declare a concorrência do worker explicitamente')
        replicas = positive((service.get('deploy') or {}).get('replicas'), 1)
        platform = positive(env.get('DB_PLATFORM_POOL_SIZE'),4)+positive(env.get('DB_PLATFORM_MAX_OVERFLOW'),2,zero=True)
        tenant = positive(env.get('DB_TENANT_POOL_SIZE'),1)+positive(env.get('DB_TENANT_MAX_OVERFLOW'),1,zero=True)
        cache = positive(env.get('TENANT_ENGINE_CACHE_MAX'),8)
        per_process = platform+tenant*cache
        limit = positive(env.get('DB_CONNECTION_BUDGET_PER_PROCESS'),24)
        if per_process > limit:
            raise ValueError(f'{name}: pools {per_process} excedem limite {limit} por processo')
        rows.append({'service':name,'processes':processes,'replicas':replicas,
                     'per_process':per_process,'maximum_pooled':per_process*processes*replicas})
    if not rows:
        raise ValueError('Nenhum serviço API/worker reconhecido no JSON do Compose')
    pooled=sum(row['maximum_pooled'] for row in rows)
    available=args.max_connections-args.reserved
    planned=pooled+args.operational_margin
    safe=planned <= available*0.8
    print(json.dumps({'services':rows,'pooled_total':pooled,'operational_margin':args.operational_margin,
                      'planned_total':planned,'ordinary_capacity':available,
                      'status':'OK' if safe else 'REVIEW_REQUIRED',
                      'note':'Não inclui réplicas externas ao Compose nem processos de outras aplicações.'},
                     indent=2,ensure_ascii=False))
    return 0 if safe else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError):
        # Do not echo raw environment values / full input on invalid configuration.
        print('Configuração inválida ou orçamento excedido; revise limites, concorrência e réplicas.',file=sys.stderr)
        raise SystemExit(2)
