#!/usr/bin/env bash
set -euo pipefail

python -m compileall apps/api/app apps/api/tests
(
  cd apps/api
  pytest -q
)
python - <<'PY'
import json
from pathlib import Path
for path in Path('.').rglob('package.json'):
    json.loads(path.read_text(encoding='utf-8'))
print('JSON package files: OK')
PY

echo 'Scheduler Pro local validation: OK'
