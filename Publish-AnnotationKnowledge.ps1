[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter()]
  [string]$MarketplaceRoot,

  [Parameter()]
  [string]$WorkspaceRoot,

  [Parameter()]
  [string]$SourceKnowledgeBase,

  [Parameter()]
  [string]$Python,

  [Parameter()]
  [string]$CodexCli,

  [Parameter()]
  [switch]$CheckOnly,

  [Parameter()]
  [switch]$SkipTests,

  [Parameter()]
  [switch]$SkipBundle,

  [Parameter()]
  [switch]$SkipInstall
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-Python {
  param([string]$ExplicitPath, [string]$Root)

  if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
    $resolved = [System.IO.Path]::GetFullPath($ExplicitPath)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
      throw "Python was not found: $resolved"
    }
    return $resolved
  }

  $command = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -ne $command -and [string]$command.Source -notmatch '[\\/]WindowsApps[\\/]') {
    return [string]$command.Source
  }

  $candidates = [System.Collections.Generic.List[string]]::new()
  if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    $candidates.Add((Join-Path $env:CODEX_HOME 'runtimes\codex-primary-runtime\dependencies\python\python.exe'))
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $candidates.Add((Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
  }
  $cursor = [System.IO.DirectoryInfo][System.IO.Path]::GetFullPath($Root)
  for ($depth = 0; $depth -lt 6 -and $null -ne $cursor; $depth++) {
    $candidates.Add((Join-Path $cursor.FullName 'codex-home\runtimes\codex-primary-runtime\dependencies\python\python.exe'))
    $cursor = $cursor.Parent
  }
  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      return $candidate
    }
  }
  throw 'A real Python runtime could not be located. Pass -Python with the full path to python.exe.'
}

function Resolve-SystemSkillRoot {
  param([string]$Name, [string]$Root)

  $candidates = [System.Collections.Generic.List[string]]::new()
  if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    $candidates.Add((Join-Path $env:CODEX_HOME "skills\.system\$Name"))
  }
  if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $candidates.Add((Join-Path $env:USERPROFILE ".codex\skills\.system\$Name"))
  }
  $cursor = [System.IO.DirectoryInfo][System.IO.Path]::GetFullPath($Root)
  for ($depth = 0; $depth -lt 6 -and $null -ne $cursor; $depth++) {
    $candidates.Add((Join-Path $cursor.FullName "codex-home\skills\.system\$Name"))
    $cursor = $cursor.Parent
  }
  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path -LiteralPath (Join-Path $candidate 'SKILL.md') -PathType Leaf) {
      return $candidate
    }
  }
  throw "Required Codex system skill was not found: $Name"
}

function Invoke-Python {
  param([string[]]$Arguments)
  & $script:pythonExe @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
  }
}

function Ensure-PythonModule {
  param([string]$Module, [string]$Package, [string]$TargetDirectory)

  if (Test-Path -LiteralPath $TargetDirectory -PathType Container) {
    $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) { $TargetDirectory } elseif (($env:PYTHONPATH -split ';') -notcontains $TargetDirectory) { "$TargetDirectory;$env:PYTHONPATH" } else { $env:PYTHONPATH }
  }
  $previousPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  & $script:pythonExe -c "import $Module" 2>$null
  $importExitCode = $LASTEXITCODE
  $ErrorActionPreference = $previousPreference
  if ($importExitCode -eq 0) {
    return
  }
  New-Item -ItemType Directory -Path $TargetDirectory -Force | Out-Null
  Write-Host "Installing validation dependency $Package into $TargetDirectory"
  & $script:pythonExe -m pip install --disable-pip-version-check --target $TargetDirectory $Package
  if ($LASTEXITCODE -ne 0) {
    throw "Could not install validation dependency: $Package"
  }
  $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) { $TargetDirectory } else { "$TargetDirectory;$env:PYTHONPATH" }
  $previousPreference = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  & $script:pythonExe -c "import $Module"
  $importExitCode = $LASTEXITCODE
  $ErrorActionPreference = $previousPreference
  if ($importExitCode -ne 0) {
    throw "Validation dependency is still unavailable after installation: $Module"
  }
}

$effectiveMarketplaceRoot = if ([string]::IsNullOrWhiteSpace($MarketplaceRoot)) { $PSScriptRoot } else { $MarketplaceRoot }
$root = [System.IO.Path]::GetFullPath($effectiveMarketplaceRoot)
$workspace = if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { Split-Path -Parent $root } else { [System.IO.Path]::GetFullPath($WorkspaceRoot) }
$env:CODEX_SHARED_MARKETPLACE_ROOT = $root
$env:CODEX_SHARED_WORKSPACE_ROOT = $workspace
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$script:pythonExe = Resolve-Python -ExplicitPath $Python -Root $root
$pluginCreator = Resolve-SystemSkillRoot -Name 'plugin-creator' -Root $root
$skillCreator = Resolve-SystemSkillRoot -Name 'skill-creator' -Root $root
$releaseTool = Join-Path $root 'tools\release_annotation_knowledge_base.py'
$packSyncTool = Join-Path $root 'tools\sync_skill_pack_versions.py'
$doctor = Join-Path $root 'Test-PersonalSkillMarketplace.ps1'

if ($CheckOnly) {
  Invoke-Python -Arguments @($releaseTool, '--check')
  Invoke-Python -Arguments @($packSyncTool, '--check')
  & $doctor -MarketplaceRoot $root
  exit $LASTEXITCODE
}

$source = if (-not [string]::IsNullOrWhiteSpace($SourceKnowledgeBase)) {
  [System.IO.Path]::GetFullPath($SourceKnowledgeBase)
}
else {
  $runtime = Join-Path $workspace '.sc-annotation-knowledge\published\current\cell-annotation-knowledge-base.v2.json'
  if (Test-Path -LiteralPath $runtime -PathType Leaf) { $runtime } else { Join-Path $root 'shared\sc-annotation-evidence-core\knowledge-base\cell-annotation-knowledge-base.v2.json' }
}

if (-not $PSCmdlet.ShouldProcess($root, "Publish approved annotation knowledge base from $source")) {
  return
}

Invoke-Python -Arguments @($releaseTool, '--source', $source)
$env:SC_ANNOTATION_KB_PATH = Join-Path $root 'shared\sc-annotation-evidence-core\knowledge-base\cell-annotation-knowledge-base.v2.json'

$cachebuster = [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
$cachebusterTool = Join-Path $pluginCreator 'scripts\update_plugin_cachebuster.py'
$annotationPlugins = @('sc-major-celltype-annotation-auto', 'sc-marker-cluster-annotation-auto')
foreach ($id in $annotationPlugins) {
  Invoke-Python -Arguments @($cachebusterTool, (Join-Path $root "plugins\$id"), '--cachebuster', $cachebuster)
}
Invoke-Python -Arguments @($packSyncTool)

Ensure-PythonModule -Module 'yaml' -Package 'PyYAML==6.0.2' -TargetDirectory (Join-Path $root 'tmp\python-validation-packages')

foreach ($id in $annotationPlugins) {
  $pluginRoot = Join-Path $root "plugins\$id"
  $skillRoot = Join-Path $pluginRoot "skills\$id"
  Invoke-Python -Arguments @((Join-Path $skillCreator 'scripts\quick_validate.py'), $skillRoot)
  Invoke-Python -Arguments @((Join-Path $pluginCreator 'scripts\validate_plugin.py'), $pluginRoot)
}

if (-not $SkipTests) {
  $testRoot = Join-Path $root ("tmp\annotation-knowledge-tests\" + $cachebuster)
  New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
  Invoke-Python -Arguments @(
    (Join-Path $root 'plugins\sc-marker-cluster-annotation-auto\skills\sc-marker-cluster-annotation-auto\tests\run_registered_regressions.py'),
    '--work-dir', (Join-Path $testRoot 'registered')
  )
  Invoke-Python -Arguments @(
    (Join-Path $root 'plugins\sc-major-celltype-annotation-auto\skills\sc-major-celltype-annotation-auto\tests\test_major_builder.py'),
    '--work-dir', (Join-Path $testRoot 'major')
  )
  Invoke-Python -Arguments @((Join-Path $root 'shared\sc-annotation-case-registry\tests\test_case_registry.py'))
}

Invoke-Python -Arguments @($releaseTool, '--check')
Invoke-Python -Arguments @($packSyncTool, '--check')
& $doctor -MarketplaceRoot $root
if ($LASTEXITCODE -ne 0) {
  throw 'Marketplace doctor failed after annotation knowledge publication.'
}

Invoke-Python -Arguments @($releaseTool, '--publish-runtime')

if (-not $SkipBundle) {
  & (Join-Path $root 'New-PersonalSkillBundle.ps1') -MarketplaceRoot $root -BundleName 'personal-codex-skills-current'
  if ($LASTEXITCODE -ne 0) {
    throw 'Portable bundle generation failed.'
  }
}

if (-not $SkipInstall) {
  $syncArguments = @{}
  if (-not [string]::IsNullOrWhiteSpace($CodexCli)) {
    $syncArguments.CodexCli = $CodexCli
  }
  & (Join-Path $root 'tools\Sync-SharedCodexSkills.ps1') @syncArguments
  if ($LASTEXITCODE -ne 0) {
    throw 'Local Codex plugin synchronization failed.'
  }
}

Write-Host "Published annotation knowledge base from: $source"
Write-Host "Annotation plugin cachebuster: $cachebuster"
Write-Host 'All release gates passed. Review and commit the Git changes, then push normally.'
