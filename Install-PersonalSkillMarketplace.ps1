[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$MarketplaceRoot,
  [string]$CodexCli,
  [string]$Python,
  [switch]$SkipDoctor,
  [switch]$SkipUserEnvironment
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($(if ($MarketplaceRoot) { $MarketplaceRoot } else { $PSScriptRoot }))
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
$arguments = @((Join-Path $root 'tools\install_personal_skill_marketplace.py'), '--marketplace-root', $root)
if ($CodexCli) { $arguments += @('--codex-cli', $CodexCli) }
if ($SkipDoctor) { $arguments += '--skip-doctor' }
if ($SkipUserEnvironment) { $arguments += '--skip-user-config' }
if ($WhatIfPreference) { $arguments += '--dry-run' }
& $pythonExe @arguments
exit $LASTEXITCODE
