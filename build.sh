#!/bin/bash
set -e

echo "=== Current directory ==="
pwd
ls -la

echo "=== Building React frontend ==="
cd frontend && npm install --legacy-peer-deps && npm run build && cd ..
echo "=== Frontend build complete ==="
ls -la frontend/build/index.html

echo "=== Installing Python dependencies ==="
python3 -m pip install -r backend/requirements.txt
echo "=== All done ==="
