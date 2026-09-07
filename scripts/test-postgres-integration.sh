#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "error: Docker is not installed." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "error: Docker is installed, but its daemon is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

image="${TROLLEY_TEST_POSTGRES_IMAGE:-postgres:16-alpine}"
container="trolley-postgres-test-$$"
password="trolley-test-password"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "Starting disposable PostgreSQL container ($image)..."
docker run --detach --rm \
  --name "$container" \
  --publish 127.0.0.1::5432 \
  --env POSTGRES_DB=trolley_test \
  --env POSTGRES_USER=trolley_test \
  --env POSTGRES_PASSWORD="$password" \
  "$image" >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$container" pg_isready \
    --username trolley_test --dbname trolley_test >/dev/null 2>&1; then
    break
  fi
  if ! docker inspect "$container" >/dev/null 2>&1; then
    echo "error: PostgreSQL container exited during startup." >&2
    exit 1
  fi
  sleep 1
done

if ! docker exec "$container" pg_isready \
  --username trolley_test --dbname trolley_test >/dev/null 2>&1; then
  echo "error: PostgreSQL did not become ready within 60 seconds." >&2
  docker logs "$container" >&2 || true
  exit 1
fi

port="$(docker port "$container" 5432/tcp | awk -F: 'NR == 1 {print $NF}')"
if [[ -z "$port" ]]; then
  echo "error: Could not determine the disposable PostgreSQL port." >&2
  exit 1
fi

python_bin="${PYTHON:-.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then
  python_bin="python"
fi

export TROLLEY_TEST_POSTGRES_URL="postgresql://trolley_test:${password}@127.0.0.1:${port}/trolley_test"
echo "Running PostgreSQL integration tests on an isolated database..."
"$python_bin" -m pytest -q tests/test_postgres_integration.py
