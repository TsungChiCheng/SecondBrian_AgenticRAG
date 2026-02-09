#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Stopping stack..."
docker compose down

echo "Removing data volumes (Postgres & Qdrant)..."
docker volume rm secondbrian_agenticrag_pgdata secondbrian_agenticrag_qdrant_data || true

echo "Building images without cache..."
docker compose build --no-cache

echo "Starting stack..."
docker compose up

# echo "Done. Health checks:"
# echo "API:    http://localhost:8001/health"
# echo "UI:     http://localhost:8000/health"
# echo "Vector: http://localhost:8002/collection/stats"
