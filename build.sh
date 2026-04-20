#!/bin/bash
set -e

echo "=== Current directory ==="
pwd
ls -la

echo "=== Building React frontend ==="
npm install --prefix frontend --legacy-peer-deps
npm run build --prefix frontend
echo "=== Frontend build complete ==="
ls -la frontend/build/index.html

echo "=== Installing Python dependencies ==="
pip install -r backend/requirements.txt
echo "=== All done ==="
