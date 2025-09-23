#!/usr/bin/env bash
# Sparse wrapper: run sparse recursively on a directory or on given .c files.
# Usage: bash sparse.sh <path|files...>
set -euo pipefail
if ! command -v sparse >/dev/null 2>&1; then
  echo "sparse not installed. On Debian/Ubuntu: sudo apt-get install sparse" >&2
  exit 2
fi
if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <dir|files...>" >&2
  exit 1
fi
args=("-Wno-transparent-union" "-Wno-address-space")
scan() {
  local d="$1"
  find "$d" -type f -name '*.c' -print0 | xargs -0 -r -n1 sparse "${args[@]}" --
}
if [[ $# -eq 1 && -d $1 ]]; then
  scan "$1"
else
  for f in "$@"; do sparse "${args[@]}" -- "$f"; done
fi

