#!/usr/bin/env bash
set -Eeuo pipefail

# Run everything the release workflow does, except the deploy.
#
# .github/workflows/release.yml is workflow_dispatch-only and its last step
# SSHes into production, so it cannot be rehearsed with `act` without risking a
# real deploy. This mirrors the safe steps instead -- validate, build both
# frontends, stamp both version.json files, and package the three tarballs --
# which is where CI actually fails in practice (tests, vue-tsc, a version stamp
# deploy_remote.sh cannot grep).
#
# The stamps and tarballs are throwaway: CI creates its own from a clean
# checkout. They are removed on exit so a fake version never lingers in the
# tree, where it could be served by a later local build or committed by mistake.
#
# usage: scripts/rehearse_release.sh [VERSION]

VERSION="${1:-local-rehearsal}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STAGE_DIR="$(mktemp -d)"
FRONTEND_STAMP="$REPO_ROOT/frontend/dist/version.json"
APP_STAMP="$REPO_ROOT/app-frontend-dist/version.json"

cleanup() {
  rm -rf "$STAGE_DIR"
  rm -f "$FRONTEND_STAMP" "$APP_STAMP"
}
trap cleanup EXIT

step() { printf '\n=== %s ===\n' "$1"; }

# CI installs from requirements.txt on a clean runner. Locally the venv already
# has them, and it pins 3.11 like the workflow does -- the system interpreter
# may be a different version without fastapi, which fails at import time and
# looks like a broken test suite.
PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
[[ -x "$PYTHON" ]] || PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "no .venv interpreter found; create one and pip install -r requirements.txt" >&2
  exit 1
fi

step "Validate backend ($("$PYTHON" -V 2>&1))"
"$PYTHON" -m compileall -q main.py app schemas.py
"$PYTHON" -m unittest discover -s tests

# npm ci is skipped: it wipes and reinstalls node_modules, which costs minutes
# and is not what breaks releases. `npm run build` runs vue-tsc first, so type
# errors still surface here.
step "Build frontend (PC)"
(cd frontend && npm run build)

step "Build app frontend"
(cd app-frontend && npm run build)

step "Stamp release"
stamp() {
  cat > "$1" <<EOF
{"version":"$VERSION","released_at":"$(date -Iseconds)","source":"$(git rev-parse HEAD)"}
EOF
}
stamp "$FRONTEND_STAMP"
stamp "$APP_STAMP"

step "Package release"
tar -czf "$STAGE_DIR/backend.tar.gz" main.py schemas.py database.py models.py requirements.txt app alembic alembic.ini scripts tests
tar -czf "$STAGE_DIR/frontend.tar.gz" -C frontend/dist .
tar -czf "$STAGE_DIR/app-frontend.tar.gz" -C app-frontend-dist .
ls -l "$STAGE_DIR"

# The same greps deploy_remote.sh runs on the host. A stamp it cannot match
# fails readiness there and rolls the release back, so assert it here.
step "Verify version stamps survive packaging"
for bundle in frontend app-frontend; do
  extracted="$(tar -xzOf "$STAGE_DIR/$bundle.tar.gz" ./version.json)"
  if grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"$VERSION\"" <<<"$extracted"; then
    echo "  $bundle.tar.gz -> version grep MATCH"
  else
    echo "  $bundle.tar.gz -> version grep FAILED: $extracted" >&2
    exit 1
  fi
done

printf '\nRehearsal of %s passed. Deploy step not run.\n' "$VERSION"
