"""Deck Card Widget alpha.2 bridge for DMS/FGF QR-data toggling.

Local file IPC only. Never changes the per-card .buttstore value.
"""
from __future__ import annotations
import json
import os
import tempfile
import time
from pathlib import Path

_COMMAND = 'dms_qr_display_command.json'
_STATUS = 'dms_qr_display_status.json'


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf8'))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError, TypeError):
        return {}


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.qr-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as file:
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def attach(app):
    """Call once at the end of PerspectiveConsoleApp.__init__."""
    from sys import modules
    module = modules[app.__class__.__module__]
    runtime = Path(module.RUNTIME_DIR)
    runtime.mkdir(parents=True, exist_ok=True)
    app._dms_qr_command = runtime / _COMMAND
    app._dms_qr_status = runtime / _STATUS
    app._dms_qr_seq = int(_read(app._dms_qr_command).get('seq', 0) or 0)
    app._dms_qr_error = ''

    def tick():
        try:
            command = _read(app._dms_qr_command)
            seq = int(command.get('seq', 0) or 0)
            if seq > app._dms_qr_seq:
                app._dms_qr_seq = seq
                try:
                    if command.get('command') != 'set_live_qr_data':
                        raise ValueError('Unsupported QR-data command')
                    enabled = command.get('payload', {}).get('enabled')
                    if type(enabled) is not bool:
                        raise ValueError('Expected boolean enabled flag')
                    app.set_live_qr_data(enabled)
                    app._dms_qr_error = ''
                except Exception as exc:
                    app._dms_qr_error = str(exc)
                    app.status_var.set('QR-data bridge: ' + app._dms_qr_error)
            snapshot = app.get_display_mode_status()
            _write(app._dms_qr_status, {
                'schema': 'dms.qr-display/1', 'heartbeat': time.time(),
                'pid': os.getpid(), 'ack_seq': app._dms_qr_seq,
                'last_error': app._dms_qr_error,
                **snapshot,
            })
        except Exception as exc:
            print('[Deck QR bridge]', exc)
        finally:
            if app.root.winfo_exists():
                app.root.after(650, tick)
    app.root.after(250, tick)
