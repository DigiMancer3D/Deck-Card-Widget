#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ./launch_3dcp_console_venv.sh "$@"
