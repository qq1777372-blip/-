#!/usr/bin/env bash
set -Eeuo pipefail

# Deploy a release onto the production host.
#
# Runs as the unprivileged login user (ubuntu) and escalates with sudo for every
# write: /srv/fastapiproject is owned by fastapiproject with UMask=027, so the
# login user cannot even cd into it. Every command that touches APP_DIR is
# wrapped, including reads -- a bare `test -f` under APP_DIR fails too.
#
# Both frontends are handled. The PC build (/ui/) lives in frontend/dist and the
# mobile App (/app/) in app-frontend-dist; each ships its own version.json, and
# /health/ready refuses to come up green unless both are present and match.

if [[ $# -lt 2 ]]; then
  echo "usage: deploy_remote.sh VERSION STAGE_DIR [APP_VERSION]" >&2
  exit 2
fi

VERSION="$1"
STAGE_DIR="$2"
APP_VERSION="${3:-}"
APP_DIR="/srv/fastapiproject"
OWNER="fastapiproject:fastapiproject"
SERVICE="fastapiproject.service"
BACKUP_DIR="$APP_DIR/deploy-backups/release-$VERSION"
FRONTEND_BACKUP="$APP_DIR/frontend/dist.bak-release-$VERSION"
APP_BACKUP="$APP_DIR/app-frontend-dist.bak-release-$VERSION"
VENV_PYTHON="$APP_DIR/.venv/bin/python"

# Staging dir belongs to the login user, so these are deliberately un-sudoed.
test -f "$STAGE_DIR/backend.tar.gz"
test -f "$STAGE_DIR/frontend.tar.gz"
HAS_APP_BUNDLE=0
if [[ -f "$STAGE_DIR/app-frontend.tar.gz" ]]; then
  HAS_APP_BUNDLE=1
fi

if [[ $HAS_APP_BUNDLE -eq 1 && -z "$APP_VERSION" ]]; then
  echo "app-frontend.tar.gz was staged but no APP_VERSION was given" >&2
  exit 2
fi

sudo mkdir -p "$BACKUP_DIR"

rollback() {
  echo "Deployment of $VERSION failed; rolling back" >&2
  if sudo test -f "$BACKUP_DIR/backend.tar.gz"; then
    sudo tar -xzf "$BACKUP_DIR/backend.tar.gz" -C "$APP_DIR"
  fi
  if sudo test -d "$FRONTEND_BACKUP"; then
    sudo rm -rf "$APP_DIR/frontend/dist"
    sudo cp -a "$FRONTEND_BACKUP" "$APP_DIR/frontend/dist"
  fi
  if sudo test -d "$APP_BACKUP"; then
    sudo rm -rf "$APP_DIR/app-frontend-dist"
    sudo cp -a "$APP_BACKUP" "$APP_DIR/app-frontend-dist"
  fi
  sudo chown -R "$OWNER" "$APP_DIR/app" "$APP_DIR/frontend/dist" "$APP_DIR/app-frontend-dist"
  sudo systemctl restart "$SERVICE"
}
trap rollback ERR

# ----------------------------------------------------------------- back up
sudo tar -czf "$BACKUP_DIR/backend.tar.gz" -C "$APP_DIR" \
  main.py schemas.py database.py models.py requirements.txt app alembic alembic.ini
sudo rm -rf "$FRONTEND_BACKUP"
sudo cp -a "$APP_DIR/frontend/dist" "$FRONTEND_BACKUP"
if [[ $HAS_APP_BUNDLE -eq 1 ]]; then
  sudo rm -rf "$APP_BACKUP"
  sudo cp -a "$APP_DIR/app-frontend-dist" "$APP_BACKUP"
fi

# --------------------------------------------------------------- stage new
sudo tar -xzf "$STAGE_DIR/backend.tar.gz" -C "$APP_DIR"

FRONTEND_STAGE="$APP_DIR/frontend/dist.stage-$VERSION"
sudo rm -rf "$FRONTEND_STAGE"
sudo mkdir -p "$FRONTEND_STAGE"
sudo tar -xzf "$STAGE_DIR/frontend.tar.gz" -C "$FRONTEND_STAGE"
sudo grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"$VERSION\"" "$FRONTEND_STAGE/version.json"

APP_STAGE="$APP_DIR/app-frontend-dist.stage-$VERSION"
if [[ $HAS_APP_BUNDLE -eq 1 ]]; then
  sudo rm -rf "$APP_STAGE"
  sudo mkdir -p "$APP_STAGE"
  sudo tar -xzf "$STAGE_DIR/app-frontend.tar.gz" -C "$APP_STAGE"
  sudo grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"$APP_VERSION\"" "$APP_STAGE/version.json"
fi

# ---------------------------------------------------------------- validate
sudo "$VENV_PYTHON" -m py_compile \
  "$APP_DIR/main.py" \
  "$APP_DIR/app/api/routes/health.py" \
  "$APP_DIR/app/api/routes/server_status.py"
sudo "$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
sudo sh -c "cd '$APP_DIR' && '$VENV_PYTHON' -m unittest discover -s tests -v"

# ------------------------------------------------------------------ swap in
sudo rm -rf "$APP_DIR/frontend/dist"
sudo mv "$FRONTEND_STAGE" "$APP_DIR/frontend/dist"
if [[ $HAS_APP_BUNDLE -eq 1 ]]; then
  sudo rm -rf "$APP_DIR/app-frontend-dist"
  sudo mv "$APP_STAGE" "$APP_DIR/app-frontend-dist"
fi
sudo chown -R "$OWNER" "$APP_DIR/app" "$APP_DIR/frontend/dist" "$APP_DIR/app-frontend-dist"
sudo systemctl restart "$SERVICE"

# ------------------------------------------------------------------- verify
for attempt in {1..20}; do
  if sudo "$VENV_PYTHON" "$APP_DIR/scripts/verify_release.py" \
    http://127.0.0.1:8000 "$VERSION" "$APP_VERSION"; then
    trap - ERR
    sudo systemctl is-active --quiet "$SERVICE"
    echo "Release $VERSION is healthy"
    exit 0
  fi
  sleep 1
done

false
