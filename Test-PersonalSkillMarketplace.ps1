[CmdletBinding()]
param(
  [string]$MarketplaceRoot,
  [string]$Python,
  [switch]$Json
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($(if ($MarketplaceRoot) { $MarketplaceRoot } else { $PSScriptRoot }))
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
$arguments = @((Join-Path $root 'tools\test_personal_skill_marketplace.py'), '--marketplace-root', $root)
if ($Json) { $arguments += '--json' }
& $pythonExe @arguments
exit $LASTEXITCODE
