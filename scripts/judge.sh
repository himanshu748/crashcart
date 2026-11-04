#!/bin/sh
# No installation, .env, licence or external account is required.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON_COMMAND="${PYTHON:-python3}"
"$PYTHON_COMMAND" -c 'import sys; sys.exit("CrashCart requires Python 3.11 or newer") if sys.version_info < (3,11) else None'
exec "$PYTHON_COMMAND" -m crashcart.judge "$@"
