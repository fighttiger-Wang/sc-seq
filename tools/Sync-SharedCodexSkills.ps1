[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter()]
  [string]$CodexCli,

  [Parameter()]
  [string]$WorkspaceRoot,

  [Parameter()]
  [string]$CodexHome,

  [Parameter()]
  [switch]$SkipDoctor,

  [Parameter()]
  [switch]$SkipUserEnvironment,

  [Parameter()]
  [switch]$ReplaceLocationConfig
)

$ErrorActionPreference = 'Stop'
$marketplaceRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $marketplaceRoot 'Install-PersonalSkillMarketplace.ps1'

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
  throw "Portable installer was not found: $installer"
}

$arguments = @{
  MarketplaceRoot = $marketplaceRoot
  SkipDoctor = $SkipDoctor
  SkipUserEnvironment = $SkipUserEnvironment
}
if (-not [string]::IsNullOrWhiteSpace($CodexCli)) {
  $arguments.CodexCli = $CodexCli
}
if (-not [string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
  $arguments.WorkspaceRoot = $WorkspaceRoot
}
if (-not [string]::IsNullOrWhiteSpace($CodexHome)) {
  $arguments.CodexHome = $CodexHome
}
if ($ReplaceLocationConfig) {
  $arguments.ReplaceLocationConfig = $true
}
if ($WhatIfPreference) {
  $arguments.WhatIf = $true
}

& $installer @arguments
exit $LASTEXITCODE
