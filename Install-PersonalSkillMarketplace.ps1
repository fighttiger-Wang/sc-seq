[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$MarketplaceRoot,
  [string]$WorkspaceRoot,
  [string]$CodexHome,
  [string]$CodexCli,
  [string]$Python,
  [switch]$SkipDoctor,
  [switch]$SkipUserEnvironment,
  [switch]$ReplaceLocationConfig,
  [switch]$ReplaceMarketplaceRegistration
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($(if ($MarketplaceRoot) { $MarketplaceRoot } else { $PSScriptRoot }))
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
$arguments = @((Join-Path $root 'tools\install_personal_skill_marketplace.py'), '--marketplace-root', $root)
if ($WorkspaceRoot) { $arguments += @('--workspace-root', $WorkspaceRoot) }
if ($CodexHome) { $arguments += @('--codex-home', $CodexHome) }
if ($CodexCli) { $arguments += @('--codex-cli', $CodexCli) }
if ($SkipDoctor) { $arguments += '--skip-doctor' }
if ($SkipUserEnvironment) { $arguments += '--skip-user-config' }
if ($ReplaceLocationConfig) { $arguments += '--replace-location-config' }
if ($ReplaceMarketplaceRegistration) { $arguments += '--replace-marketplace-registration' }
if ($WhatIfPreference) { $arguments += '--dry-run' }
& $pythonExe @arguments
exit $LASTEXITCODE
