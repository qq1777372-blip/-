param(
  [Parameter(Mandatory = $true)]
  [string]$Version,
  [string]$DeployHost = "121.196.150.21",
  [string]$DeployUser = "root",
  [string]$SshKey = "C:\Users\Administrator\.ssh\xiaoxu.pem"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$Artifacts = Join-Path $ProjectRoot ".release\$Version"
$RemoteStage = "/tmp/ruoshop-release-$Version"

if (Test-Path -LiteralPath $Artifacts) {
  throw "Release artifact directory already exists: $Artifacts"
}
New-Item -ItemType Directory -Path $Artifacts -Force | Out-Null

py -3 -m py_compile `
  (Join-Path $ProjectRoot "main.py") `
  (Join-Path $ProjectRoot "schemas.py") `
  (Join-Path $ProjectRoot "app\api\routes\health.py") `
  (Join-Path $ProjectRoot "app\api\routes\server_status.py")
if ($LASTEXITCODE -ne 0) { throw "Backend validation failed" }

Push-Location $FrontendRoot
try {
  npm ci
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally {
  Pop-Location
}

$VersionJson = @{
  version = $Version
  released_at = (Get-Date).ToString("o")
  source = (git -C $ProjectRoot rev-parse --short HEAD 2>$null)
} | ConvertTo-Json
$Utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
  (Join-Path $FrontendRoot "dist\version.json"),
  $VersionJson,
  $Utf8WithoutBom
)

tar -czf (Join-Path $Artifacts "backend.tar.gz") -C $ProjectRoot `
  main.py schemas.py database.py models.py requirements.txt app alembic alembic.ini scripts tests
tar -czf (Join-Path $Artifacts "frontend.tar.gz") -C (Join-Path $FrontendRoot "dist") .

$Remote = "$DeployUser@$DeployHost"
ssh -i $SshKey -o StrictHostKeyChecking=no $Remote "mkdir -p '$RemoteStage'"
scp -i $SshKey -o StrictHostKeyChecking=no `
  (Join-Path $Artifacts "backend.tar.gz") `
  (Join-Path $Artifacts "frontend.tar.gz") `
  (Join-Path $ProjectRoot "scripts\deploy_remote.sh") `
  "${Remote}:${RemoteStage}/"
ssh -i $SshKey -o StrictHostKeyChecking=no $Remote `
  "bash '$RemoteStage/deploy_remote.sh' '$Version' '$RemoteStage'"
if ($LASTEXITCODE -ne 0) { throw "Remote deployment failed and rollback was requested" }

Write-Host "Release $Version deployed and passed readiness checks."
