[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$MarketplaceRoot,
  [string]$WorkspaceRoot,
  [string]$SourceKnowledgeBase,
  [string]$Python,
  [string]$CodexCli,
  [switch]$CheckOnly,
  [switch]$SkipTests,
  [switch]$SkipBundle,
  [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($(if ($MarketplaceRoot) { $MarketplaceRoot } else { $PSScriptRoot }))
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
$arguments = @((Join-Path $root 'tools\publish_annotation_knowledge.py'), '--marketplace-root', $root)
if ($WorkspaceRoot) { $arguments += @('--workspace-root', $WorkspaceRoot) }
if ($SourceKnowledgeBase) { $arguments += @('--source', $SourceKnowledgeBase) }
if ($CodexCli) { $arguments += @('--codex-cli', $CodexCli) }
if ($CheckOnly) { $arguments += '--check-only' }
if ($SkipTests) { $arguments += '--skip-tests' }
if ($SkipBundle) { $arguments += '--skip-bundle' }
if ($SkipInstall) { $arguments += '--skip-install' }
if (-not $PSCmdlet.ShouldProcess($root, 'Publish annotation knowledge with cross-platform release gates')) { return }
& $pythonExe @arguments
exit $LASTEXITCODE
