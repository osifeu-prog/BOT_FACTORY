param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("start","stop","status","test","logs")]
  [string]$cmd
)

$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root ".uvicorn.pid"

function LoadEnvLocal {
  $envFile = Join-Path $root ".env.local"
  if (-not (Test-Path $envFile)) { return }
  Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    if ($line.StartsWith("#")) { return }
    $kv = $line -split "=", 2
    if ($kv.Count -ne 2) { return }
    $name = $kv[0].Trim()
    $val  = $kv[1].Trim()
    if ($name) { Set-Item -Path ("Env:" + $name) -Value $val }
  }
}

function Get-UvPid {
  if (Test-Path $pidFile) {
    $p = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($p -match '^\d+$') { return [int]$p }
  }
  return $null
}

function Is-Running([int]$p) {
  if (-not $p) { return $false }
  return $null -ne (Get-Process -Id $p -ErrorAction SilentlyContinue)
}

function Stop-ByPidFile {
  $p = Get-UvPid
  if (Is-Running $p) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 300
  }
  Remove-Item $pidFile -ErrorAction SilentlyContinue
}

function Stop-ByPort {
  # best-effort stop anything listening on 8000 (in case pid file missing)
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

if ($cmd -eq "stop") {
  Stop-ByPidFile
  Stop-ByPort
  Write-Host "stopped"
  exit 0
}

if ($cmd -eq "start") {
  & $PSCommandPath stop | Out-Null

  # auto-load env vars from .env.local
  LoadEnvLocal

  $py = Join-Path $root ".venv\Scripts\python.exe"
  if (-not (Test-Path $py)) { throw "venv python not found: $py" }

  $args = @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--log-level","info")

  $p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $root -PassThru -WindowStyle Minimized
  Set-Content -Path $pidFile -Value $p.Id -NoNewline

  Start-Sleep -Seconds 1
  Write-Host "started pid=$($p.Id)"
  exit 0
}

if ($cmd -eq "status") {
  $p = Get-UvPid
  if (Is-Running $p) {
    Write-Host "running pid=$p"
  } else {
    Write-Host "not running"
  }
  exit 0
}

if ($cmd -eq "logs") {
  $p = Get-UvPid
  if (-not (Is-Running $p)) {
    Write-Host "not running"
    exit 1
  }
  Get-Process -Id $p | Select-Object Id,ProcessName,Path
  exit 0
}

if ($cmd -eq "test") {
  $base = "http://127.0.0.1:8000"

  # Prefer iwr; fallback to curl.exe
  try { $h = (Invoke-WebRequest "$base/health" -TimeoutSec 3).Content } catch { $h = "health: FAIL ($($_.Exception.Message))" }
  try { $r = (Invoke-WebRequest "$base/ready"  -TimeoutSec 3).Content } catch { $r = "ready:  FAIL ($($_.Exception.Message))" }

  if (-not $h -or $h -match '^health:\s*FAIL') {
    try { $h2 = & curl.exe -s --max-time 3 "$base/health" } catch { $h2 = "" }
    if ($h2) { $h = $h2 }
  }
  if (-not $r -or $r -match '^ready:\s*FAIL') {
    try { $r2 = & curl.exe -s --max-time 3 "$base/ready" } catch { $r2 = "" }
    if ($r2) { $r = $r2 }
  }

  Write-Host "health=$h"
  Write-Host "ready=$r"
  exit 0
}
