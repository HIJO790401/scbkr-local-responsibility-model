#!/usr/bin/env sh
set -eu
python -m pip install -e .
npm --prefix apps/web install --package-lock=false
printf '\nSCBKR P12 setup complete. Backend: http://localhost:8787 Web: http://localhost:5500\n'
