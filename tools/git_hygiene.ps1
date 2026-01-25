# tools/git_hygiene.ps1
# Terminal-safe Git hygiene for BOT_FACTORY (no nested heredocs)
$ErrorActionPreference="Stop"

function Write-Utf8NoBomLf([string]$Path,[string]$Text){
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  $full=[System.IO.Path]::GetFullPath($Path)
  $dir=[System.IO.Path]::GetDirectoryName($full)
  if($dir){[System.IO.Directory]::CreateDirectory($dir)|Out-Null}
  $lf=$Text -replace "`r`n","`n" -replace "`r","`n"
  [System.IO.File]::WriteAllText($full,$lf,$utf8NoBom)
}

Write-Host "== Git Hygiene (safe) ==" -ForegroundColor Cyan
$repoRoot=(git rev-parse --show-toplevel) 2>$null
if(-not $repoRoot){ throw "Not inside a git repo." }
Set-Location $repoRoot
Write-Host "Repo root: $repoRoot" -ForegroundColor DarkGray

# A) Normalize .gitignore + ensure patterns exist
$giPath = Join-Path $repoRoot ".gitignore"
if(-not (Test-Path $giPath)){ throw ".gitignore not found at repo root." }

$gi = (Get-Content $giPath -Raw) -replace "`r`n","`n" -replace "`r","`n"
$header = "# local runtime / smoke artifacts (local-only)"
$blockLines = @(
  "/.run_port.txt",
  "/_smoke_logs/",
  "/tools/smoke*.ps1",
  "/tools/run_8012*.ps1",
  "/tools/stop_*.ps1",
  "/tools/run_local_a.ps1",
  "/utils/**",
  "app/bot/investor_wallet_bot.py.bak"
)

if($gi -notmatch [regex]::Escape($header)){
  $gi = $gi.TrimEnd() + "`n`n" + $header + "`n" + (($blockLines -join "`n").Trim()) + "`n"
}else{
  foreach($line in $blockLines){
    if($line -and ($gi -notmatch ("(?m)^" + [regex]::Escape($line) + "$"))){
      $gi = $gi.TrimEnd() + "`n" + $line + "`n"
    }
  }
}

# write back UTF-8 no BOM + LF
Write-Utf8NoBomLf $giPath $gi

# sanity: no CR
$bytes=[System.IO.File]::ReadAllBytes($giPath)
if($bytes -contains 13){ throw "CRLF detected in .gitignore after normalization" }

git add --renormalize .gitignore | Out-Null
Write-Host "OK: .gitignore normalized + ignore patterns ensured" -ForegroundColor Green

# B) Clean local artifacts safely (never delete tools/run_local.ps1)
$ErrorActionPreference="SilentlyContinue"
Remove-Item -Force .\.run_port.txt -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\_smoke_logs -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\smoke*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\run_8012*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\stop_*.ps1 -ErrorAction SilentlyContinue
Remove-Item -Force .\tools\run_local_a.ps1 -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\utils -ErrorAction SilentlyContinue
$ErrorActionPreference="Stop"
Write-Host "OK: local artifacts cleaned" -ForegroundColor Green

# C) Run repo check if exists
if(Test-Path ".\tools\precommit_check.py"){
  Write-Host "`n-- running precommit_check.py --" -ForegroundColor Yellow
  python .\tools\precommit_check.py
}

Write-Host "`n-- git status --" -ForegroundColor Yellow
git status --porcelain | Out-Host
Write-Host "All done." -ForegroundColor Cyan