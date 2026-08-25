[CmdletBinding()]
param(
  [Parameter()]
  [string]$MarketplaceRoot,

  [Parameter()]
  [switch]$Json
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$errors = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
  param(
    [string]$Name,
    [bool]$Passed,
    [string]$Detail,
    [ValidateSet('error', 'warning')]
    [string]$Severity = 'error'
  )

  $checks.Add([pscustomobject]@{
      name = $Name
      passed = $Passed
      severity = $Severity
      detail = $Detail
    })

  if (-not $Passed) {
    if ($Severity -eq 'warning') {
      $warnings.Add("${Name}: $Detail")
    }
    else {
      $errors.Add("${Name}: $Detail")
    }
  }
}

function Read-JsonFile {
  param([string]$Path, [string]$Label)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Add-Check -Name $Label -Passed $false -Detail "Missing file: $Path"
    return $null
  }

  try {
    $value = Get-Content -Raw -Encoding utf8 -LiteralPath $Path | ConvertFrom-Json
    Add-Check -Name $Label -Passed $true -Detail $Path
    return $value
  }
  catch {
    Add-Check -Name $Label -Passed $false -Detail $_.Exception.Message
    return $null
  }
}

$effectiveMarketplaceRoot = if ([string]::IsNullOrWhiteSpace($MarketplaceRoot)) { $PSScriptRoot } else { $MarketplaceRoot }
$root = [System.IO.Path]::GetFullPath($effectiveMarketplaceRoot)
$packPath = Join-Path $root 'skill-pack.json'
$marketplacePath = Join-Path $root '.agents\plugins\marketplace.json'
$compatibilityPath = Join-Path $root '.codex-plugin\marketplace.json'

$pack = Read-JsonFile -Path $packPath -Label 'skill-pack manifest'
$marketplace = Read-JsonFile -Path $marketplacePath -Label 'canonical marketplace manifest'
$compatibility = Read-JsonFile -Path $compatibilityPath -Label 'compatibility marketplace manifest'

$expectedIds = @()
if ($null -ne $pack) {
  $expectedIds = @($pack.plugins | ForEach-Object { [string]$_.id })
  Add-Check -Name 'expected plugin count' -Passed ($expectedIds.Count -eq [int]$pack.expectedPluginCount) -Detail "Expected $($pack.expectedPluginCount), found $($expectedIds.Count) in skill-pack.json"
  Add-Check -Name 'unique skill-pack ids' -Passed (($expectedIds | Sort-Object -Unique).Count -eq $expectedIds.Count) -Detail 'Duplicate plugin ids exist in skill-pack.json'
}

if ($null -ne $marketplace) {
  $marketplaceIds = @($marketplace.plugins | ForEach-Object { [string]$_.name })
  Add-Check -Name 'marketplace name' -Passed ([string]$marketplace.name -eq [string]$pack.name) -Detail "Expected '$($pack.name)', found '$($marketplace.name)'"
  Add-Check -Name 'canonical plugin count' -Passed ($marketplaceIds.Count -eq $expectedIds.Count) -Detail "Expected $($expectedIds.Count), found $($marketplaceIds.Count)"
  Add-Check -Name 'canonical plugin set' -Passed (-not (Compare-Object ($expectedIds | Sort-Object) ($marketplaceIds | Sort-Object))) -Detail 'Canonical marketplace plugin ids differ from skill-pack.json'

  foreach ($entry in @($marketplace.plugins)) {
    $entryOk = (
      [string]$entry.source.source -eq 'local' -and
      [string]$entry.source.path -eq "./plugins/$($entry.name)" -and
      @('AVAILABLE', 'INSTALLED_BY_DEFAULT', 'NOT_AVAILABLE') -contains [string]$entry.policy.installation -and
      @('ON_INSTALL', 'ON_USE') -contains [string]$entry.policy.authentication -and
      -not [string]::IsNullOrWhiteSpace([string]$entry.category)
    )
    Add-Check -Name "marketplace entry $($entry.name)" -Passed $entryOk -Detail 'Source path or required policy/category fields are invalid'
  }
}

if ($null -ne $compatibility -and $null -ne $marketplace) {
  $compatibilityIds = @($compatibility.plugins | ForEach-Object { [string]$_.name })
  Add-Check -Name 'compatibility marketplace name' -Passed ([string]$compatibility.name -eq [string]$marketplace.name) -Detail 'The two marketplace manifests use different names'
  Add-Check -Name 'compatibility plugin set' -Passed (-not (Compare-Object ($expectedIds | Sort-Object) ($compatibilityIds | Sort-Object))) -Detail 'The compatibility marketplace does not contain the same 11 plugins'
}

foreach ($plugin in @($pack.plugins)) {
  $id = [string]$plugin.id
  $pluginRoot = Join-Path $root "plugins\$id"
  $pluginManifestPath = Join-Path $pluginRoot '.codex-plugin\plugin.json'
  $skillRoot = Join-Path $pluginRoot "skills\$id"
  $skillPath = Join-Path $skillRoot 'SKILL.md'
  $agentPath = Join-Path $skillRoot 'agents\openai.yaml'

  Add-Check -Name "plugin directory $id" -Passed (Test-Path -LiteralPath $pluginRoot -PathType Container) -Detail $pluginRoot
  $pluginManifest = Read-JsonFile -Path $pluginManifestPath -Label "plugin manifest $id"

  if ($null -ne $pluginManifest) {
    $manifestOk = (
      [string]$pluginManifest.name -eq $id -and
      [string]$pluginManifest.version -eq [string]$plugin.version -and
      -not [string]::IsNullOrWhiteSpace([string]$pluginManifest.description) -and
      -not [string]::IsNullOrWhiteSpace([string]$pluginManifest.author.name) -and
      -not [string]::IsNullOrWhiteSpace([string]$pluginManifest.interface.displayName) -and
      [string]$pluginManifest.skills -eq './skills/'
    )
    Add-Check -Name "plugin metadata $id" -Passed $manifestOk -Detail "Manifest name/version/required fields do not match skill-pack.json (expected version $($plugin.version))"
  }

  Add-Check -Name "skill file $id" -Passed (Test-Path -LiteralPath $skillPath -PathType Leaf) -Detail $skillPath
  if (Test-Path -LiteralPath $skillPath -PathType Leaf) {
    $skillText = Get-Content -Raw -Encoding utf8 -LiteralPath $skillPath
    $frontmatterMatch = [regex]::Match($skillText, '(?s)\A---\s*\r?\n(.*?)\r?\n---')
    $hasName = $frontmatterMatch.Success -and $frontmatterMatch.Groups[1].Value -match "(?m)^name:\s*$([regex]::Escape($id))\s*$"
    $hasDescription = $frontmatterMatch.Success -and $frontmatterMatch.Groups[1].Value -match '(?m)^description:\s*\S'
    Add-Check -Name "skill frontmatter $id" -Passed ($hasName -and $hasDescription) -Detail 'SKILL.md must start with matching name and a non-empty description'
  }

  Add-Check -Name "skill UI metadata $id" -Passed (Test-Path -LiteralPath $agentPath -PathType Leaf) -Detail $agentPath
  if ($null -ne $pluginManifest -and (Test-Path -LiteralPath $agentPath -PathType Leaf)) {
    $agentText = Get-Content -Raw -Encoding utf8 -LiteralPath $agentPath
    $displayMatch = [regex]::Match($agentText, '(?m)^\s*display_name:\s*["'']?([^"''\r\n]+)')
    $agentDisplay = if ($displayMatch.Success) { $displayMatch.Groups[1].Value.Trim() } else { '' }
    $pluginDisplay = [string]$pluginManifest.interface.displayName
    $displayOk = $pluginDisplay -eq $agentDisplay -and $pluginDisplay -match '^\d{2} \u00b7 .+$'
    Add-Check -Name "numbered display name $id" -Passed $displayOk -Detail "plugin.json='$pluginDisplay'; openai.yaml='$agentDisplay'"
  }
}

foreach ($sharedPath in @($pack.sharedPaths)) {
  $resolvedSharedPath = Join-Path $root ([string]$sharedPath -replace '/', '\')
  Add-Check -Name "shared path $sharedPath" -Passed (Test-Path -LiteralPath $resolvedSharedPath -PathType Container) -Detail $resolvedSharedPath
}

$evidenceRoot = Join-Path $root 'shared\sc-annotation-evidence-core'
$evidenceVersion = Read-JsonFile -Path (Join-Path $evidenceRoot 'VERSION.json') -Label 'annotation evidence version'
$evidenceConfig = Read-JsonFile -Path (Join-Path $evidenceRoot 'annotation-evidence-config.v1.json') -Label 'annotation evidence config'
$knowledgeRoot = Join-Path $evidenceRoot 'knowledge-base'
$knowledgeBase = Read-JsonFile -Path (Join-Path $knowledgeRoot 'cell-annotation-knowledge-base.v2.json') -Label 'annotation knowledge base'
$knowledgeManifest = Read-JsonFile -Path (Join-Path $knowledgeRoot 'knowledge-base.manifest.json') -Label 'annotation knowledge manifest'

if ($null -ne $evidenceVersion -and $null -ne $evidenceConfig -and $null -ne $knowledgeBase -and $null -ne $knowledgeManifest) {
  $coreText = Get-Content -Raw -Encoding utf8 -LiteralPath (Join-Path $evidenceRoot 'annotation_evidence_core.py')
  $coreMatch = [regex]::Match($coreText, '(?m)^CORE_VERSION\s*=\s*["'']([^"'']+)["'']')
  $versionOk = (
    $coreMatch.Success -and
    [string]$evidenceVersion.core_version -eq [string]$coreMatch.Groups[1].Value -and
    [string]$evidenceVersion.config_version -eq [string]$evidenceConfig.config_version -and
    [string]$evidenceVersion.knowledge_base_version -eq [string]$knowledgeBase.knowledge_base_version -and
    [string]$evidenceVersion.knowledge_base_version -eq [string]$knowledgeManifest.knowledge_base_version
  )
  Add-Check -Name 'annotation canonical versions' -Passed $versionOk -Detail "VERSION core=$($evidenceVersion.core_version), config=$($evidenceVersion.config_version), kb=$($evidenceVersion.knowledge_base_version); config=$($evidenceConfig.config_version); kb=$($knowledgeBase.knowledge_base_version); manifest=$($knowledgeManifest.knowledge_base_version)"

  $manifestHashErrors = [System.Collections.Generic.List[string]]::new()
  foreach ($property in @($knowledgeManifest.sha256.PSObject.Properties)) {
    $path = Join-Path $knowledgeRoot ([string]$property.Name -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      $manifestHashErrors.Add("missing:$($property.Name)")
      continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$property.Value).ToLowerInvariant()) {
      $manifestHashErrors.Add("hash:$($property.Name)")
    }
  }
  Add-Check -Name 'annotation knowledge hashes' -Passed ($manifestHashErrors.Count -eq 0) -Detail ($manifestHashErrors -join '; ')

  $snapshotFiles = [ordered]@{
    'annotation_evidence_core.py' = @('scripts', 'annotation_evidence_core.py')
    'knowledge_base.py' = @('scripts', 'knowledge_base.py')
    'annotation-evidence-config.v1.json' = @('references', 'annotation-evidence-config.v1.json')
    'evidence-scoring-policy.md' = @('references', 'evidence-scoring-policy.md')
    'knowledge-base/cell-annotation-knowledge-base.v2.json' = @('references', 'cell-annotation-knowledge-base.v2.json')
    'knowledge-base/legacy-migration.v2.json' = @('references', 'legacy-migration.v2.json')
    'knowledge-base/knowledge-base.manifest.json' = @('references', 'knowledge-base.manifest.json')
  }
  foreach ($id in @('sc-major-celltype-annotation-auto', 'sc-marker-cluster-annotation-auto')) {
    $skillRoot = Join-Path $root "plugins\$id\skills\$id"
    $snapshot = Read-JsonFile -Path (Join-Path $skillRoot 'references\annotation-evidence-core.snapshot.json') -Label "annotation snapshot $id"
    if ($null -eq $snapshot) {
      continue
    }
    $metadataOk = (
      [string]$snapshot.core_version -eq [string]$evidenceVersion.core_version -and
      [string]$snapshot.config_version -eq [string]$evidenceVersion.config_version -and
      [string]$snapshot.knowledge_base_version -eq [string]$evidenceVersion.knowledge_base_version -and
      [string]$snapshot.snapshot_contract -eq [string]$evidenceVersion.snapshot_contract -and
      [string]$snapshot.canonical_source -eq 'shared/sc-annotation-evidence-core'
    )
    Add-Check -Name "annotation snapshot metadata $id" -Passed $metadataOk -Detail "snapshot core=$($snapshot.core_version), config=$($snapshot.config_version), kb=$($snapshot.knowledge_base_version), source=$($snapshot.canonical_source)"

    $snapshotErrors = [System.Collections.Generic.List[string]]::new()
    foreach ($entry in $snapshotFiles.GetEnumerator()) {
      $sourcePath = Join-Path $evidenceRoot ([string]$entry.Key -replace '/', '\')
      $destinationPath = Join-Path (Join-Path $skillRoot $entry.Value[0]) $entry.Value[1]
      if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf) -or -not (Test-Path -LiteralPath $destinationPath -PathType Leaf)) {
        $snapshotErrors.Add("missing:$($entry.Key)")
        continue
      }
      $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
      $destinationHash = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
      $snapshotProperty = $snapshot.files.PSObject.Properties[[string]$entry.Key]
      $recordedHash = if ($null -ne $snapshotProperty) { ([string]$snapshotProperty.Value).ToLowerInvariant() } else { '' }
      if ($sourceHash -ne $destinationHash -or $sourceHash -ne $recordedHash) {
        $snapshotErrors.Add("mismatch:$($entry.Key)")
      }
    }
    Add-Check -Name "annotation snapshot files $id" -Passed ($snapshotErrors.Count -eq 0) -Detail ($snapshotErrors -join '; ')
  }
}

$forbiddenFiles = @(Get-ChildItem -LiteralPath $root -File -Recurse -Force | Where-Object {
  $_.FullName -notmatch '[\\/](logs|outputs|tmp|\.git|__pycache__)[\\/]' -and
  $_.Name -match '(^\.env($|\.)|\.pem$|\.key$|credentials|secrets?|\.sqlite3(?:-wal|-shm)?$)'
})
Add-Check -Name 'secret-like files' -Passed ($forbiddenFiles.Count -eq 0) -Detail (($forbiddenFiles | ForEach-Object { $_.FullName } | Select-Object -First 10) -join '; ')

$absolutePathHits = [System.Collections.Generic.List[string]]::new()
$textExtensions = @('.md', '.json', '.yaml', '.yml', '.ps1', '.py', '.R', '.txt')
Get-ChildItem -LiteralPath $root -File -Recurse -Force | Where-Object {
  $textExtensions -contains $_.Extension -and
  $_.FullName -notmatch '[\\/](logs|outputs|tmp|\.git|__pycache__)[\\/]'
} | ForEach-Object {
  $content = Get-Content -Raw -Encoding utf8 -LiteralPath $_.FullName -ErrorAction SilentlyContinue
  $normalizedContent = ($content -replace '\\\\', '\') -replace '/', '\'
  if (
    $normalizedContent -match '(?i)\b[A-Z]:\\Users\\[^\\]+\\' -or
    $normalizedContent -match '(?i)\b[A-Z]:\\A002-Codex\\\u5DE5\u4F5C\u533A\\'
  ) {
    $absolutePathHits.Add($_.FullName)
  }
}
Add-Check -Name 'machine-specific absolute paths' -Passed ($absolutePathHits.Count -eq 0) -Detail (($absolutePathHits | Select-Object -First 10) -join '; ') -Severity warning

foreach ($runtime in @('powershell', 'git', 'codex', 'python', 'Rscript')) {
  $runtimeCommand = Get-Command $runtime -ErrorAction SilentlyContinue | Select-Object -First 1
  $found = $null -ne $runtimeCommand
  if ($runtime -in @('codex', 'python') -and $found -and [string]$runtimeCommand.Source -match '[\\/]WindowsApps[\\/]') {
    $found = $false
  }
  Add-Check -Name "runtime $runtime" -Passed $found -Detail "$runtime is not currently available in PATH" -Severity warning
}

$summary = [pscustomobject]@{
  marketplaceRoot = $root
  marketplace = if ($null -ne $pack) { [string]$pack.name } else { $null }
  expectedPluginCount = if ($null -ne $pack) { [int]$pack.expectedPluginCount } else { 0 }
  errors = @($errors)
  warnings = @($warnings)
  passed = ($errors.Count -eq 0)
  checks = @($checks)
}

if ($Json) {
  $summary | ConvertTo-Json -Depth 6
}
else {
  Write-Host "Personal skill marketplace: $root"
  foreach ($check in $checks) {
    $status = if ($check.passed) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
    if ($check.passed) {
      Write-Host ('[{0}] {1}' -f $status, $check.name)
    }
    else {
      Write-Host ('[{0}] {1}: {2}' -f $status, $check.name, $check.detail)
    }
  }
  Write-Host "Result: $($errors.Count) error(s), $($warnings.Count) warning(s)."
}

if ($errors.Count -gt 0) {
  exit 1
}

exit 0
