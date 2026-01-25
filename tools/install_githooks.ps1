# tools/install_githooks.ps1
# Install repo git hooks (sh) without pwsh dependency.
$ErrorActionPreference="Stop"

function Write-Utf8NoBomLfLines([string]$Path,[string[]]$Lines){
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  $full=[System.IO.Path]::GetFullPath($Path)
  $dir=[System.IO.Path]::GetDirectoryName($full)
  if($dir){ [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
  $text = ($Lines -join "`n") + "`n"
  $text = $text -replace "`r`n","`n" -replace "`r","`n"
  [System.IO.File]::WriteAllText($full,$text,$utf8NoBom)
}

$repoRoot=(git rev-parse --show-toplevel) 2>$null
if(-not $repoRoot){ throw "Not inside a git repo." }
Set-Location $repoRoot

$hooksDir = Join-Path $repoRoot ".githooks"
New-Item -ItemType Directory -Force $hooksDir | Out-Null

$preCommit = @(
  "#!/bin/sh"
  "set -eu"
  "if [ -f `"tools/precommit_check.py`" ]; then"
  "  python tools/precommit_check.py"
  "else"
  "  echo `"WARN: tools/precommit_check.py not found; skipping.`" 1>&2"
  "fi"
  "git diff --cached --check >/dev/null"
)

$prePush = @(
  "#!/bin/sh"
  "set -eu"
  "echo `"pre-push: running repo checks...`""
  "if [ -f `"tools/precommit_check.py`" ]; then"
  "  python tools/precommit_check.py"
  "fi"
  "git status --porcelain"
)

Write-Utf8NoBomLfLines (Join-Path $hooksDir "pre-commit") $preCommit
Write-Utf8NoBomLfLines (Join-Path $hooksDir "pre-push")   $prePush

git config core.hooksPath .githooks
Write-Host "OK: hooks installed (.githooks) using sh hooks." -ForegroundColor Green
git config --show-origin --get core.hooksPath | Out-Host
