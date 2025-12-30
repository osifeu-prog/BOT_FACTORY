$ErrorActionPreference = "Stop"

function _GetScriptDir {
  # works for dot-sourcing in PS 5.1
  if ($PSScriptRoot -and $PSScriptRoot.Trim().Length -gt 0) { return $PSScriptRoot }
  return Split-Path -Parent $MyInvocation.MyCommand.Path
}

function _GetVaultPaths([string]$Profile) {
  if ([string]::IsNullOrWhiteSpace($Profile)) { $Profile = "local" }
  $dir = Join-Path (_GetScriptDir) ".vault"
  $file = Join-Path $dir ("secrets.{0}.json" -f $Profile)
  return @{ Dir = $dir; File = $file; Profile = $Profile }
}

function _WriteUtf8NoBomLf([string]$Path, [string]$Content) {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  $lf = $Content -replace "`r`n","`n"
  [System.IO.File]::WriteAllText($Path, $lf, $utf8NoBom)
}

function _EncryptPlain([string]$plain) {
  # DPAPI user-scope (same Windows user)
  $sec = ConvertTo-SecureString -String $plain -AsPlainText -Force
  return ConvertFrom-SecureString -SecureString $sec
}

function _DecryptToPlain([string]$enc) {
  $sec = ConvertTo-SecureString -String $enc
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

function _ParseTextToHashtable([string]$Text) {
  $data = @{}

  if ($null -eq $Text) { return $data }
  $t = $Text.Trim()

  # JSON
  if ($t.StartsWith("{")) {
    $obj = $t | ConvertFrom-Json
    foreach ($p in $obj.PSObject.Properties) {
      $k = [string]$p.Name
      $v = [string]$p.Value
      if (-not [string]::IsNullOrWhiteSpace($k) -and -not [string]::IsNullOrWhiteSpace($v)) {
        $data[$k] = $v
      }
    }
    return $data
  }

  # dotenv-ish / raw text
  $lines = $Text -split "`n"
  foreach ($line in $lines) {
    $s = ($line -replace "`r","").Trim()
    if ($s.Length -eq 0) { continue }
    if ($s.StartsWith("#")) { continue }

    # support: export KEY=VALUE
    if ($s.StartsWith("export ")) { $s = $s.Substring(7).Trim() }

    $k = $null
    $v = $null

    # KEY=VALUE
    if ($s -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") {
      $k = $Matches[1]
      $v = $Matches[2]
    }
    # KEY: VALUE
    elseif ($s -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)\s*$") {
      $k = $Matches[1]
      $v = $Matches[2]
    }
    else {
      continue
    }

    $k = $k.Trim()
    $v = $v.Trim()

    # strip wrapping quotes
    if ($v.Length -ge 2) {
      if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
        $v = $v.Substring(1, $v.Length-2)
      }
    }

    if ([string]::IsNullOrWhiteSpace($k)) { continue }
    if ([string]::IsNullOrWhiteSpace($v)) { continue }

    $data[$k] = $v
  }

  return $data
}

function Save-SecretsFromText {
  param(
    [Parameter(Mandatory=$true)][string]$Text,
    [string]$Profile = "local"
  )

  $p = _GetVaultPaths $Profile
  New-Item -ItemType Directory -Force -Path $p.Dir | Out-Null

  $plain = _ParseTextToHashtable $Text
  if ($plain.Keys.Count -eq 0) { throw "No variables found. Expect JSON or KEY=VALUE lines." }

  $enc = @{}
  foreach ($k in $plain.Keys) {
    $enc[$k] = _EncryptPlain ([string]$plain[$k])
  }

  $json = $enc | ConvertTo-Json -Depth 10
  _WriteUtf8NoBomLf $p.File $json

  Write-Host "Saved encrypted vault (DPAPI user-scope):" -ForegroundColor Green
  Write-Host $p.File -ForegroundColor Green
}

function Save-SecretsFromFile {
  param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [string]$Profile = "local"
  )
  if (-not (Test-Path $InputPath)) { throw "Input file not found: $InputPath" }
  $text = Get-Content $InputPath -Raw
  Save-SecretsFromText -Text $text -Profile $Profile
}

function Save-SecretsFromClipboard {
  param([string]$Profile = "local")
  $text = Get-Clipboard -Raw
  Save-SecretsFromText -Text $text -Profile $Profile
}

function Load-SecretsToEnv {
  param([string]$Profile = "local")

  $p = _GetVaultPaths $Profile
  if (-not (Test-Path $p.File)) { throw "Vault not found: $($p.File). Run Save-SecretsFromFile/Clipboard first." }

  $raw = Get-Content $p.File -Raw
  $obj = $raw | ConvertFrom-Json

  foreach ($prop in $obj.PSObject.Properties) {
    $name = [string]$prop.Name
    $enc  = [string]$prop.Value
    $plain = _DecryptToPlain $enc
    [Environment]::SetEnvironmentVariable($name, $plain, "Process")
  }

  Write-Host ("Loaded secrets into ENV (Process scope) for profile: {0}" -f $p.Profile) -ForegroundColor Green
}

function Show-SecretsStatus {
  param(
    [string[]]$Names,
    [string]$Profile = "local"
  )

  $p = _GetVaultPaths $Profile
  $exists = Test-Path $p.File

  Write-Host ("Profile: {0}" -f $p.Profile) -ForegroundColor Cyan
  Write-Host ("Vault:    {0}" -f $p.File) -ForegroundColor Cyan
  Write-Host ("Exists:   {0}" -f $exists) -ForegroundColor Cyan

  if (-not $Names) { return }

  $rows = foreach ($n in $Names) {
    $val = [Environment]::GetEnvironmentVariable($n, "Process")
    [pscustomobject]@{ Name = $n; InProcessEnv = (-not [string]::IsNullOrWhiteSpace($val)) }
  }
  $rows | Format-Table -AutoSize
}

function Open-SecretsInputFile {
  param(
    [string]$InputPath = (Join-Path (_GetScriptDir) "railway.vars.txt")
  )
  if (-not (Test-Path $InputPath)) {
    _WriteUtf8NoBomLf $InputPath "# Paste Railway Variables here (JSON or KEY=VALUE).`n"
  }
  Write-Host "Opening: $InputPath" -ForegroundColor Cyan
  Start-Process notepad.exe $InputPath
}