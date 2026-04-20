#!/bin/bash
set -e

echo "=== Building React frontend ==="
cd /app/frontend
npm install --legacy-peer-deps
npm run build
echo "=== Frontend build complete ==="
ls -la /app/frontend/build/

echo "=== Installing Python dependencies ==="
cd /app/backend
pip install -r requirements.txt
echo "=== Backend dependencies installed ==="
