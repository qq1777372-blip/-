#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: deploy_remote.sh VERSION STAGE_DIR" >&2
  exit 2
fi

VERSION="$1"
STAGE_DIR="$2"
APP_DIR="/srv/fastapiproject"
BACKUP_DIR="$APP_DIR/deploy-backups/release-$VERSION"
FRONTEND_BACKUP="$APP_DIR/frontend/dist.bak-release-$VERSION"

test -f "$STAGE_DIR/backend.tar.gz"
test -f "$STAGE_DIR/frontend.tar.gz"
mkdir -p "$BACKUP_DIR/backend" "$BACKUP_DIR/frontend"

rollback() {
  echo "Health check failed; rolling back $VERSION" >&2
  if [[ -f "$BACKUP_DIR/backend.tar.gz" ]]; then
    tar -xzf "$BACKUP_DIR/backend.tar.gz" -C "$APP_DIR"
  fi
  if [[ -d "$FRONTEND_BACKUP" ]]; then
    rm -rf "$APP_DIR/frontend/dist"
    cp -a "$FRONTEND_BACKUP" "$APP_DIR/frontend/dist"
  fi
  chown -R fastapiproject:fastapiproject "$APP_DIR/app" "$APP_DIR/frontend/dist"
  systemctl restart fastapiproject.service
}
trap rollback ERR

tar -czf "$BACKUP_DIR/backend.tar.gz" -C "$APP_DIR" \
  main.py schemas.py database.py models.py requirements.txt app alembic alembic.ini
rm -rf "$FRONTEND_BACKUP"
cp -a "$APP_DIR/frontend/dist" "$FRONTEND_BACKUP"

tar -xzf "$STAGE_DIR/backend.tar.gz" -C "$APP_DIR"
rm -rf "$APP_DIR/frontend/dist.stage-$VERSION"
mkdir -p "$APP_DIR/frontend/dist.stage-$VERSION"
tar -xzf "$STAGE_DIR/frontend.tar.gz" -C "$APP_DIR/frontend/dist.stage-$VERSION"
grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"$VERSION\"" "$APP_DIR/frontend/dist.stage-$VERSION/version.json"

python3 -m py_compile "$APP_DIR/main.py" "$APP_DIR/app/api/routes/health.py" "$APP_DIR/app/api/routes/server_status.py"
cd "$APP_DIR"
"$APP_DIR/.venv/bin/python" -m unittest discover -s tests -v
rm -rf "$APP_DIR/frontend/dist"
mv "$APP_DIR/frontend/dist.stage-$VERSION" "$APP_DIR/frontend/dist"
chown -R fastapiproject:fastapiproject "$APP_DIR/app" "$APP_DIR/frontend/dist"
systemctl restart fastapiproject.service

for attempt in {1..20}; do
  if python3 "$APP_DIR/scripts/verify_release.py" http://127.0.0.1:8000 "$VERSION"; then
    trap - ERR
    systemctl is-active --quiet fastapiproject.service
    echo "Release $VERSION is healthy"
    exit 0
  fi
  sleep 1
done

false
