# tools/clean_local.ps1
# Remove local-only smoke/runtime artifacts (safe)
$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $repoRoot) { throw "Not inside a git repo." }
Set-Location $repoRoot

$ErrorActionPreference = "SilentlyContinue"
Remove-Item -Force .\.run_port.txt -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\_smoke_logs -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\smoke*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\run_*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\stop_*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\run_local_a.ps1 -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\utils -ErrorAction SilentlyContinue
$ErrorActionPreference = "Stop"

Write-Host "OK: cleaned local artifacts." -ForegroundColor Green
