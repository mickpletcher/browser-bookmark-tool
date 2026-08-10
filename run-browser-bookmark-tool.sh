#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BBT_PYTHON=${BBT_PYTHON:-python3}
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    BBT_PYTHON="$SCRIPT_DIR/.venv/bin/python"
fi
if ! "$BBT_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Browser Bookmark Tool requires Python 3.10 or newer." >&2
    exit 1
fi
exec "$BBT_PYTHON" "$SCRIPT_DIR/browser_bookmark_sync.py" "$@"
