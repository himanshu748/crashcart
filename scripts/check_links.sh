#!/bin/sh
# Public GET checks plus local documentation links; requires Python 3 and curl.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$root/scripts/check_links.py" "$@"
