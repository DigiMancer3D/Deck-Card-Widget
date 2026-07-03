#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Deck Card Widget Display Edit acceptance"
python3 -m py_compile 3dcp_perspective_console.py
python3 - <<'PY'
from pathlib import Path
src = Path('3dcp_perspective_console.py').read_text(encoding='utf-8')
required = [
    'Display Edit',
    'DISPLAY_TEXT_DEFAULTS',
    'ensure_display_text_storage',
    'draw_display_text',
    'apply_display_text_editor',
    'Deck Card Widget - Output',
]
missing = [x for x in required if x not in src]
if missing:
    raise SystemExit(f'Missing expected Display Edit code: {missing}')
print('PASS: Display Edit code present')
print('PASS: Python compile')
PY
