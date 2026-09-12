#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

docker compose \
  --project-directory "$SCRIPT_DIR" \
  --file "$SCRIPT_DIR/compose.yml" \
  config --quiet

docker run --rm \
  --add-host host.docker.internal:host-gateway \
  curlimages/curl:8.15.0 \
  --fail --show-error --silent \
  --retry 10 --retry-delay 1 --retry-connrefused \
  http://host.docker.internal:3000/ >/dev/null

echo "Compose configuration is valid and the application is reachable at http://localhost:3000"
