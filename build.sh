#!/bin/bash
# Railway build script — builds React frontend before starting backend
set -e

echo "=== Installing frontend dependencies ==="
cd /app/frontend
yarn install --frozen-lockfile 2>/dev/null || yarn install

echo "=== Building React frontend ==="
yarn build

echo "=== Frontend build complete ==="
ls -la build/index.html

echo "=== Installing backend dependencies ==="
cd /app/backend
pip install -r requirements.txt

echo "=== Build complete ==="
