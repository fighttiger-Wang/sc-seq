[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter()]
  [string]$MarketplaceRoot = $PSScriptRoot,

  [Parameter()]
  [string]$CodexCli,

  [Parameter()]
  [switch]$SkipDoctor,

  [Parameter()]
  [switch]$SkipUserEnvironment
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-CodexCli {
  param([string]$ExplicitPath, [string]$Root)

  if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
    $resolved = [System.IO.Path]::GetFullPath($ExplicitPath)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
      throw "Codex CLI was not found: $resolved"
    }
    return $resolved
  }

  $command = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
  if (
    $null -ne $command -and
    -not [string]::IsNullOrWhiteSpace([string]$command.Source) -and
    [string]$command.Source -notmatch '[\\/]WindowsApps[\\/]'
  ) {
    return [string]$command.Source
  }

  $candidates = [System.Collections.Generic.List[string]]::new()
  if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    $candidates.Add((Join-Path $env:CODEX_HOME 'plugins\.plugin-appserver\codex.exe'))
  }

  $cursor = [System.IO.DirectoryInfo][System.IO.Path]::GetFullPath($Root)
  for ($depth = 0; $depth -lt 6 -and $null -ne $cursor; $depth++) {
    $candidates.Add((Join-Path $cursor.FullName 'codex-home\plugins\.plugin-appserver\codex.exe'))
    $cursor = $cursor.Parent
  }

  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      return $candidate
    }
  }

  throw 'Codex CLI could not be located. Add codex to PATH or pass -CodexCli with the full path to codex.exe.'
}

function Invoke-Codex {
  param([string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)

  $display = 'codex ' + ($Arguments -join ' ')
  if (-not $PSCmdlet.ShouldProcess($display, 'Run')) {
    return @()
  }

  $output = @(& $script:codexExe @Arguments 2>&1)
  $exitCode = $LASTEXITCODE
  if (-not $Quiet) {
    $output | ForEach-Object { Write-Host $_ }
  }
  if ($exitCode -ne 0 -and -not $AllowFailure) {
    throw "Command failed with exit code ${exitCode}: $display"
  }
  return $output
}

$root = [System.IO.Path]::GetFullPath($MarketplaceRoot)
$doctorPath = Join-Path $root 'Test-PersonalSkillMarketplace.ps1'
$packPath = Join-Path $root 'skill-pack.json'

if (-not $SkipDoctor) {
  if (-not (Test-Path -LiteralPath $doctorPath -PathType Leaf)) {
    throw "Doctor script was not found: $doctorPath"
  }
  & $doctorPath -MarketplaceRoot $root
  if ($LASTEXITCODE -ne 0) {
    throw 'Marketplace validation failed. Installation was not attempted.'
  }
}

$pack = Get-Content -Raw -Encoding utf8 -LiteralPath $packPath | ConvertFrom-Json
$workspaceRoot = Split-Path -Parent $root
$env:CODEX_SHARED_MARKETPLACE_ROOT = $root
$env:CODEX_SHARED_WORKSPACE_ROOT = $workspaceRoot
if (-not $SkipUserEnvironment -and $PSCmdlet.ShouldProcess('Current Windows user environment', 'Persist shared Codex marketplace and workspace paths')) {
  [Environment]::SetEnvironmentVariable('CODEX_SHARED_MARKETPLACE_ROOT', $root, 'User')
  [Environment]::SetEnvironmentVariable('CODEX_SHARED_WORKSPACE_ROOT', $workspaceRoot, 'User')
  Write-Host 'Saved CODEX_SHARED_MARKETPLACE_ROOT and CODEX_SHARED_WORKSPACE_ROOT for the current Windows user.'
}

$script:codexExe = Resolve-CodexCli -ExplicitPath $CodexCli -Root $root
Write-Host "Codex CLI: $script:codexExe"
Write-Host "Marketplace: $($pack.name)"

$registerOutput = Invoke-Codex -Arguments @('plugin', 'marketplace', 'add', $root) -AllowFailure
if (-not $WhatIfPreference) {
  $marketplaceList = Invoke-Codex -Arguments @('plugin', 'marketplace', 'list') -AllowFailure -Quiet
  $marketplaceText = $marketplaceList -join "`n"
  if ($marketplaceText -notmatch [regex]::Escape([string]$pack.name)) {
    throw "Marketplace '$($pack.name)' was not visible after registration. Registration output: $($registerOutput -join ' ')"
  }
}

foreach ($plugin in @($pack.plugins)) {
  $qualifiedName = "$($plugin.id)@$($pack.name)"
  Invoke-Codex -Arguments @('plugin', 'add', $qualifiedName) | Out-Null
}

if (-not $WhatIfPreference) {
  $pluginList = Invoke-Codex -Arguments @('plugin', 'list') -Quiet
  $pluginText = $pluginList -join "`n"
  $missing = @($pack.plugins | Where-Object { $pluginText -notmatch [regex]::Escape([string]$_.id) } | ForEach-Object { [string]$_.id })
  if ($missing.Count -gt 0) {
    throw "Codex did not report these plugins after installation: $($missing -join ', ')"
  }
}

if ($WhatIfPreference) {
  Write-Host "Dry run completed for $($pack.plugins.Count) plugins from '$($pack.name)'. No Codex or user-environment changes were made."
}
else {
  Write-Host "Installed $($pack.plugins.Count) plugins from '$($pack.name)'. Restart Codex and open a new task before testing updated skills."
}
