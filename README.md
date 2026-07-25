# RuoShop Admin

Canonical source for the RuoShop administration API and Vue frontend.

## Local validation

```bash
python -m compileall -q main.py app schemas.py
python -m unittest discover -s tests -v
cd frontend
npm ci
npm run build
```

## Health checks

- `GET /health/live`: process liveness
- `GET /health/ready`: database and frontend readiness

Production releases are built by `.github/workflows/release.yml`. The remote deploy script backs up the current backend and frontend, restarts the service, runs readiness checks, and restores the backup automatically if validation fails.

For an authenticated release from the maintainer workstation:

```powershell
.\scripts\release.ps1 -Version 2026.07.26.18
```
