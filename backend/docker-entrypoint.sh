#!/bin/sh
set -eu

if [ "$#" -ge 3 ] && \
   [ "$1" = "python" ] && \
   [ "$2" = "-m" ] && \
   [ "$3" = "app.scripts.migrate" ]; then
  exec "$@"
fi

python -m app.scripts.migrate --check
exec "$@"
