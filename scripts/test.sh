#!/usr/bin/env sh
set -eu
python -m pytest -q
npm --prefix apps/web run build
