[CmdletBinding()]
param(
  [string]$MarketplaceRoot,
  [string]$OutputDirectory,
  [string]$BundleName,
  [string]$Python
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($(if ($MarketplaceRoot) { $MarketplaceRoot } else { $PSScriptRoot }))
. (Join-Path $root 'tools\Resolve-WorkspacePython.ps1')
$pythonExe = Resolve-WorkspacePython -ExplicitPath $Python -Root $root
& $pythonExe (Join-Path $root 'tools\test_personal_skill_marketplace.py') --marketplace-root $root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$arguments = @((Join-Path $root 'tools\new_personal_skill_bundle.py'), '--marketplace-root', $root)
if ($OutputDirectory) { $arguments += @('--output-directory', $OutputDirectory) }
if ($BundleName) { $arguments += @('--bundle-name', $BundleName) }
& $pythonExe @arguments
exit $LASTEXITCODE
