param(
  [Parameter(Mandatory = $true)]
  [string]$Version,
  [string]$AppVersion = "",
  [string]$DeployHost = "152.32.174.85",
  [string]$DeployUser = "ubuntu",
  [string]$SshKey = "D:\ServerKeys\xiaoxu-ucloud-ed25519"
)

# Build, package and deploy a release to production.
#
# The default target is the UCloud Hong Kong host that actually serves
# xiaoxu666.asia. It used to default to the retired aliyun box (121.196.150.21 /
# root / xiaoxu.pem), which meant a plain `.\release.ps1 -Version x` published to
# the wrong machine.
#
# Two frontends ship from this repo: the PC console (frontend/ -> /ui/) and the
# mobile App (app-frontend/ -> /app/). Note it is app-frontend/ and not app/,
# which is already the backend Python package.
#
# The App is optional so this script keeps working before its source has been
# recovered into the repo; when app-frontend/ is present an -AppVersion is
# required, because the deployed build has to be able to prove which version it
# is.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$AppRoot = Join-Path $ProjectRoot "app-frontend"
$AiRoot = Join-Path $ProjectRoot "services\ai-workspace"
$Artifacts = Join-Path $ProjectRoot ".release\$Version"
$RemoteStage = "/tmp/ruoshop-release-$Version"

$BuildApp = Test-Path -LiteralPath (Join-Path $AppRoot "package.json")
if ($BuildApp -and [string]::IsNullOrWhiteSpace($AppVersion)) {
  throw "app-frontend/ is present, so -AppVersion is required (e.g. -AppVersion 0.8.47-alpha)"
}

if (Test-Path -LiteralPath $Artifacts) {
  throw "Release artifact directory already exists: $Artifacts"
}
New-Item -ItemType Directory -Path $Artifacts -Force | Out-Null

# The tests import fastapi, which only exists in the venv -- the system `py -3`
# fails with ModuleNotFoundError. Use the same interpreter for py_compile so a
# release is validated against the version it will actually run under.
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
  throw "Missing venv at $VenvPython. Create it with: py -3 -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

& $VenvPython -m py_compile `
  (Join-Path $ProjectRoot "main.py") `
  (Join-Path $ProjectRoot "schemas.py") `
  (Join-Path $ProjectRoot "app\api\routes\health.py") `
  (Join-Path $ProjectRoot "app\api\routes\server_status.py")
if ($LASTEXITCODE -ne 0) { throw "Backend validation failed" }

# `discover -s <abs path> -t <root>` raises "Start directory is not importable"
# because tests/ has no __init__.py. Running from the project root with a
# relative -s is the form that actually works.
Push-Location $ProjectRoot
try {
  & $VenvPython -m unittest discover -s tests
  if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
} finally {
  Pop-Location
}

function Invoke-FrontendBuild {
  param([string]$Root, [string]$Label)

  Push-Location $Root
  try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "$Label npm ci failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "$Label build failed" }
  } finally {
    Pop-Location
  }
}

function Write-VersionJson {
  param([string]$DistDir, [string]$BuildVersion)

  if (-not (Test-Path -LiteralPath $DistDir)) {
    throw "Build output missing: $DistDir"
  }
  $payload = @{
    version     = $BuildVersion
    released_at = (Get-Date).ToString("o")
    source      = (git -C $ProjectRoot rev-parse --short HEAD 2>$null)
  } | ConvertTo-Json
  $Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText((Join-Path $DistDir "version.json"), $payload, $Utf8WithoutBom)
}

Invoke-FrontendBuild -Root $FrontendRoot -Label "PC frontend"
$FrontendDist = Join-Path $FrontendRoot "dist"
Write-VersionJson -DistDir $FrontendDist -BuildVersion $Version

tar -czf (Join-Path $Artifacts "backend.tar.gz") -C $ProjectRoot `
  main.py schemas.py database.py models.py requirements.txt app alembic alembic.ini scripts tests
tar -czf (Join-Path $Artifacts "frontend.tar.gz") -C $FrontendDist .

$Payload = @(
  (Join-Path $Artifacts "backend.tar.gz"),
  (Join-Path $Artifacts "frontend.tar.gz")
)

if (-not (Test-Path -LiteralPath (Join-Path $AiRoot "server.py"))) {
  throw "AI workspace service is missing at $AiRoot"
}
tar -czf (Join-Path $Artifacts "ai-workspace.tar.gz") -C $AiRoot `
  README.md migrate_legacy_knowledge.py requirements.txt server.py test_server.py
$Payload += (Join-Path $Artifacts "ai-workspace.tar.gz")

if ($BuildApp) {
  Invoke-FrontendBuild -Root $AppRoot -Label "Mobile App"
  # app-frontend/vite.config.ts writes to ../app-frontend-dist, matching the
  # directory name main.py serves /app/ from.
  $AppDist = Join-Path $ProjectRoot "app-frontend-dist"
  Write-VersionJson -DistDir $AppDist -BuildVersion $AppVersion
  tar -czf (Join-Path $Artifacts "app-frontend.tar.gz") -C $AppDist .
  $Payload += (Join-Path $Artifacts "app-frontend.tar.gz")
} else {
  Write-Host "app-frontend/ not found; deploying backend and PC frontend only."
}

$Payload += (Join-Path $ProjectRoot "scripts\deploy_remote.sh")

$Remote = "$DeployUser@$DeployHost"
ssh -i $SshKey -o StrictHostKeyChecking=no $Remote "mkdir -p '$RemoteStage'"
scp -i $SshKey -o StrictHostKeyChecking=no $Payload "${Remote}:${RemoteStage}/"
ssh -i $SshKey -o StrictHostKeyChecking=no $Remote `
  "bash '$RemoteStage/deploy_remote.sh' '$Version' '$RemoteStage' '$AppVersion'"
if ($LASTEXITCODE -ne 0) { throw "Remote deployment failed and rollback was requested" }

Write-Host "Release $Version deployed and passed readiness checks."
