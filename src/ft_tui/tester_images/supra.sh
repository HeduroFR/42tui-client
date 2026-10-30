#!/bin/sh
set -eu
printf '%s\n' 'Rebuilding the disposable project for Linux…'
make fclean
make -B all
exec "$@"
