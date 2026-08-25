[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter()]
  [string]$CodexCli,

  [Parameter()]
  [switch]$SkipDoctor,

  [Parameter()]
  [switch]$SkipUserEnvironment
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
if ($WhatIfPreference) {
  $arguments.WhatIf = $true
}

& $installer @arguments
exit $LASTEXITCODE
