[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [ValidateSet('audit', 'install', 'update', 'repair')]
  [string]$Mode = 'install',
  [string]$WorkspaceRoot,
  [string]$CodexHome,
  [string]$CodexCli,
  [string]$Python,
  [string]$Repository = 'https://github.com/fighttiger-Wang/sc-seq.git',
  [string]$Ref,
  [switch]$Relocate
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($PSScriptRoot)
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
$script = Join-Path $root 'plugins\personal-skill-marketplace-setup\skills\personal-skill-marketplace-setup\scripts\setup.py'
$arguments = @($script, $Mode, '--marketplace-root', $root, '--repo-url', $Repository)
if ($WorkspaceRoot) { $arguments += @('--workspace-root', $WorkspaceRoot) }
if ($CodexHome) { $arguments += @('--codex-home', $CodexHome) }
if ($CodexCli) { $arguments += @('--codex-cli', $CodexCli) }
if ($Ref) { $arguments += @('--ref', $Ref) }
if ($Relocate) { $arguments += '--relocate' }
if ($WhatIfPreference) {
  $arguments += '--dry-run'
} elseif (-not $PSCmdlet.ShouldProcess($root, "$Mode workspace-local marketplace")) {
  return
}
& $pythonExe @arguments
exit $LASTEXITCODE
