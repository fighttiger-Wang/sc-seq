[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('init','register','resolve','show','list','commit','import-legacy','finalize-legacy','add-alias','merge','rollback','audit','unlock')]
    [string]$Command,
    [string]$StoreRoot = '',
    [string]$Id,
    [string]$Name,
    [ValidateSet('project','software','codebase','skill','other')]
    [string]$Type = 'other',
    [string[]]$Aliases = @(),
    [string[]]$Anchors = @(),
    [string]$Query,
    [string]$ContentPath,
    [int]$ExpectedRevision = -1,
    [ValidateSet('completed','failed','blocked','paused','in-progress','migrated')]
    [string]$Status = 'completed',
    [string]$SourcePath,
    [string]$SnapshotPath,
    [string]$SourceId,
    [string]$TargetId,
    [int]$Revision = -1,
    [switch]$ConfirmMerge,
    [switch]$ConfirmUnlock
)

$ErrorActionPreference = 'Stop'
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:HistoryLimit = 30

function Find-MarketplaceRoot {
    $cursor = Get-Item -LiteralPath $PSScriptRoot
    while ($null -ne $cursor) {
        if (Test-Path -LiteralPath (Join-Path $cursor.FullName 'skill-pack.json') -PathType Leaf) {
            return $cursor.FullName
        }
        $cursor = $cursor.Parent
    }
    return $null
}

$marketplaceRoot = Find-MarketplaceRoot
if (-not [string]::IsNullOrWhiteSpace($env:CODEX_SHARED_WORKSPACE_ROOT)) {
    $workspaceRoot = [IO.Path]::GetFullPath($env:CODEX_SHARED_WORKSPACE_ROOT)
}
elseif ($marketplaceRoot) {
    $workspaceRoot = [IO.Directory]::GetParent($marketplaceRoot).FullName
}
else {
    throw 'Shared workspace could not be resolved. Run Install-PersonalSkillMarketplace.ps1 or set CODEX_SHARED_WORKSPACE_ROOT.'
}

if (-not [string]::IsNullOrWhiteSpace($env:CODEX_SHARED_ALLOWED_ROOT)) {
    $script:AllowedRoot = [IO.Path]::GetFullPath($env:CODEX_SHARED_ALLOWED_ROOT)
}
else {
    $workspaceParent = [IO.Directory]::GetParent($workspaceRoot)
    $script:AllowedRoot = if ($null -ne $workspaceParent) { $workspaceParent.FullName } else { $workspaceRoot }
}

if ([string]::IsNullOrWhiteSpace($StoreRoot)) {
    $StoreRoot = Join-Path $workspaceRoot '.codex-handoff'
}

function Get-FullSafePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($script:AllowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must stay under $($script:AllowedRoot): $full"
    }
    return $full
}

$StoreRoot = Get-FullSafePath $StoreRoot
$RegistryPath = Join-Path $StoreRoot 'registry.json'
$EntitiesRoot = Join-Path $StoreRoot 'entities'
$LocksRoot = Join-Path $StoreRoot 'locks'
$MergedRoot = Join-Path $StoreRoot 'merged'

function Write-Utf8Atomic {
    param([string]$Path, [string]$Text)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $temp = Join-Path $parent ('.tmp-' + [Guid]::NewGuid().ToString('N'))
    [IO.File]::WriteAllText($temp, $Text, $script:Utf8NoBom)
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function ConvertTo-StableJson {
    param($Object)
    return (($Object | ConvertTo-Json -Depth 12) + [Environment]::NewLine)
}

function Initialize-Store {
    New-Item -ItemType Directory -Force -Path $StoreRoot,$EntitiesRoot,$LocksRoot,$MergedRoot | Out-Null
    if (-not (Test-Path -LiteralPath $RegistryPath)) {
        $registry = [ordered]@{
            schemaVersion = 1
            storeRoot = $StoreRoot
            historyLimit = $script:HistoryLimit
            entities = @()
        }
        Write-Utf8Atomic $RegistryPath (ConvertTo-StableJson $registry)
    }
}

function Read-Registry {
    Initialize-Store
    $registry = ([IO.File]::ReadAllText($RegistryPath, [Text.Encoding]::UTF8) | ConvertFrom-Json)
    if ($registry.schemaVersion -ne 1) { throw "Unsupported registry schema: $($registry.schemaVersion)" }
    return $registry
}

function Save-Registry {
    param($Registry)
    Write-Utf8Atomic $RegistryPath (ConvertTo-StableJson $Registry)
}

function Normalize-Id {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { throw 'Id is required.' }
    $normalized = $Value.ToLowerInvariant() -replace '[^a-z0-9]+','-'
    $normalized = $normalized.Trim('-')
    if (-not $normalized -or $normalized.Length -gt 64) { throw "Invalid normalized id: $normalized" }
    return $normalized
}

function Get-EntityDir { param([string]$EntityId) return (Join-Path $EntitiesRoot (Normalize-Id $EntityId)) }
function Get-ManifestPath { param([string]$EntityId) return (Join-Path (Get-EntityDir $EntityId) 'manifest.json') }
function Get-CurrentPath { param([string]$EntityId) return (Join-Path (Get-EntityDir $EntityId) 'CURRENT.md') }
function Get-HistoryDir { param([string]$EntityId) return (Join-Path (Get-EntityDir $EntityId) 'history') }

function Read-Manifest {
    param([string]$EntityId)
    $path = Get-ManifestPath $EntityId
    if (-not (Test-Path -LiteralPath $path)) { throw "Manifest not found for entity: $EntityId" }
    return ([IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json)
}

function Save-Manifest {
    param([string]$EntityId, $Manifest)
    Write-Utf8Atomic (Get-ManifestPath $EntityId) (ConvertTo-StableJson $Manifest)
}

function Acquire-Lock {
    param([string]$LockId)
    New-Item -ItemType Directory -Force -Path $LocksRoot | Out-Null
    $lockPath = Join-Path $LocksRoot ((Normalize-Id $LockId) + '.lock')
    try { New-Item -ItemType Directory -Path $lockPath -ErrorAction Stop | Out-Null }
    catch { throw "Concurrent or stale lock detected: $lockPath. Stop and ask the user before unlock." }
    $owner = [ordered]@{ createdAt = [DateTimeOffset]::Now.ToString('o'); processId = $PID; command = $Command }
    Write-Utf8Atomic (Join-Path $lockPath 'owner.json') (ConvertTo-StableJson $owner)
    return $lockPath
}

function Release-Lock {
    param([string]$LockPath)
    if ($LockPath -and (Test-Path -LiteralPath $LockPath)) { Remove-Item -LiteralPath $LockPath -Recurse -Force }
}

function Find-Entity {
    param($Registry, [string]$EntityId)
    $normalized = Normalize-Id $EntityId
    return @($Registry.entities | Where-Object { $_.id -eq $normalized }) | Select-Object -First 1
}

function Assert-IdentityAvailable {
    param($Registry, [string[]]$Values, [string]$ExceptId = '')
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value)) { continue }
        foreach ($entity in @($Registry.entities)) {
            if ($ExceptId -and $entity.id -eq $ExceptId) { continue }
            $owned = @($entity.id, $entity.name) + @($entity.aliases) + @($entity.anchors)
            if (@($owned | Where-Object { $_ -and $_.ToString().Equals($value, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) {
                throw "Identity value already belongs to '$($entity.id)': $value"
            }
        }
    }
}

function New-ManifestObject {
    param([string]$EntityId)
    return [ordered]@{
        schemaVersion = 1
        id = $EntityId
        currentRevision = 0
        status = 'in-progress'
        updatedAt = $null
        currentSha256 = $null
        historyLimit = $script:HistoryLimit
    }
}

function Get-Sha256 { param([string]$Path) return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }

function Get-HistoryFiles {
    param([string]$EntityId)
    $dir = Get-HistoryDir $EntityId
    if (-not (Test-Path -LiteralPath $dir)) { return @() }
    return @(Get-ChildItem -LiteralPath $dir -File -Filter 'rev-*.md' | Sort-Object Name)
}

function Enforce-HistoryLimit {
    param([string]$EntityId)
    $files = @(Get-HistoryFiles $EntityId)
    if ($files.Count -gt $script:HistoryLimit) {
        foreach ($file in @($files | Select-Object -First ($files.Count - $script:HistoryLimit))) {
            Remove-Item -LiteralPath $file.FullName -Force
        }
    }
}

function Get-HistoryPath {
    param([string]$EntityId, [int]$NewRevision, [string]$Kind)
    $stamp = [DateTimeOffset]::Now.ToString('yyyyMMddTHHmmssfffzzz').Replace(':','')
    return Join-Path (Get-HistoryDir $EntityId) ('rev-{0:D4}-{1}-{2}.md' -f $NewRevision,$stamp,$Kind)
}

function Add-ContentRevision {
    param([string]$EntityId, [string]$Text, [int]$Expected, [string]$NewStatus, [string]$Kind = 'update', [switch]$SkipTemplateValidation)
    $manifest = Read-Manifest $EntityId
    if ($Expected -ge 0 -and [int]$manifest.currentRevision -ne $Expected) {
        throw "Revision mismatch for '$EntityId': expected $Expected, actual $($manifest.currentRevision). Stop for user confirmation."
    }
    if (-not $SkipTemplateValidation) {
        foreach ($heading in @('## Goal','## Changes','## Verification','## Open issues','## Pitfalls')) {
            if (-not $Text.Contains($heading)) { throw "Missing required heading: $heading" }
        }
    }
    $newRevision = [int]$manifest.currentRevision + 1
    $historyPath = Get-HistoryPath $EntityId $newRevision $Kind
    Write-Utf8Atomic $historyPath $Text
    Write-Utf8Atomic (Get-CurrentPath $EntityId) $Text
    $manifest.currentRevision = $newRevision
    $manifest.status = $NewStatus
    $manifest.updatedAt = [DateTimeOffset]::Now.ToString('o')
    $manifest.currentSha256 = Get-Sha256 (Get-CurrentPath $EntityId)
    Save-Manifest $EntityId $manifest
    Enforce-HistoryLimit $EntityId
    return [ordered]@{ id=$EntityId; revision=$newRevision; status=$NewStatus; currentPath=(Get-CurrentPath $EntityId); historyPath=$historyPath; sha256=$manifest.currentSha256 }
}

function Add-LegacySnapshot {
    param([string]$EntityId, [string]$LegacyPath)
    $source = Get-FullSafePath $LegacyPath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Legacy source not found: $source" }
    $manifest = Read-Manifest $EntityId
    $newRevision = [int]$manifest.currentRevision + 1
    $historyPath = Get-HistoryPath $EntityId $newRevision 'legacy'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $historyPath) | Out-Null
    Copy-Item -LiteralPath $source -Destination $historyPath
    $sourceHash = Get-Sha256 $source
    $snapshotHash = Get-Sha256 $historyPath
    if ($sourceHash -ne $snapshotHash) { Remove-Item -LiteralPath $historyPath -Force; throw 'Legacy snapshot hash verification failed.' }
    $manifest.currentRevision = $newRevision
    $manifest.status = 'migrated'
    $manifest.updatedAt = [DateTimeOffset]::Now.ToString('o')
    Save-Manifest $EntityId $manifest
    Enforce-HistoryLimit $EntityId
    return [ordered]@{ id=$EntityId; revision=$newRevision; sourcePath=$source; snapshotPath=$historyPath; sha256=$sourceHash }
}

Initialize-Store

switch ($Command) {
    'init' {
        [ordered]@{ storeRoot=$StoreRoot; registryPath=$RegistryPath; historyLimit=$script:HistoryLimit } | ConvertTo-Json
    }
    'register' {
        $lock = Acquire-Lock 'registry'
        try {
            $registry = Read-Registry
            $entityId = Normalize-Id $Id
            if (Find-Entity $registry $entityId) { throw "Entity already exists: $entityId" }
            if ([string]::IsNullOrWhiteSpace($Name)) { throw 'Name is required.' }
            $cleanAliases = @($Aliases | Where-Object { $_ } | Select-Object -Unique)
            $cleanAnchors = @($Anchors | Where-Object { $_ } | ForEach-Object { Get-FullSafePath $_ } | Select-Object -Unique)
            Assert-IdentityAvailable $registry (@($entityId,$Name) + $cleanAliases + $cleanAnchors)
            $entity = [ordered]@{ id=$entityId; name=$Name; type=$Type; aliases=$cleanAliases; anchors=$cleanAnchors; createdAt=[DateTimeOffset]::Now.ToString('o') }
            $registry.entities = @($registry.entities) + @($entity)
            Save-Registry $registry
            New-Item -ItemType Directory -Force -Path (Get-HistoryDir $entityId) | Out-Null
            Save-Manifest $entityId (New-ManifestObject $entityId)
            $entity | ConvertTo-Json -Depth 8
        } finally { Release-Lock $lock }
    }
    'resolve' {
        if ([string]::IsNullOrWhiteSpace($Query)) { throw 'Query is required.' }
        $registry = Read-Registry
        $q = $Query.Trim()
        $qPath = $null
        try { if ([IO.Path]::IsPathRooted($q)) { $qPath = [IO.Path]::GetFullPath($q) } } catch {}
        $results = foreach ($entity in @($registry.entities)) {
            $exact = @($entity.id,$entity.name) + @($entity.aliases)
            $score = 0
            $reason = ''
            if (@($exact | Where-Object { $_ -and $_.ToString().Equals($q,[StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { $score=100; $reason='exact-name-or-alias' }
            elseif ($qPath -and @($entity.anchors | Where-Object { $_ -and ([IO.Path]::GetFullPath($_)).Equals($qPath,[StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { $score=100; $reason='exact-anchor' }
            elseif (@($exact | Where-Object { $_ -and ($_.ToString().IndexOf($q,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or $q.IndexOf($_.ToString(),[StringComparison]::OrdinalIgnoreCase) -ge 0) }).Count -gt 0) { $score=50; $reason='partial-name-or-alias' }
            elseif ($qPath -and @($entity.anchors | Where-Object { $_ -and ($qPath.StartsWith([IO.Path]::GetFullPath($_),[StringComparison]::OrdinalIgnoreCase) -or ([IO.Path]::GetFullPath($_)).StartsWith($qPath,[StringComparison]::OrdinalIgnoreCase)) }).Count -gt 0) { $score=40; $reason='related-anchor' }
            if ($score -gt 0) { [ordered]@{ id=$entity.id; name=$entity.name; type=$entity.type; score=$score; reason=$reason } }
        }
        $ordered = @($results | Sort-Object @{Expression='score';Descending=$true},id)
        $unique = ($ordered.Count -eq 1 -and $ordered[0].score -eq 100)
        [ordered]@{ query=$q; unique=$unique; candidates=$ordered } | ConvertTo-Json -Depth 8
    }
    'show' {
        $registry = Read-Registry
        $entity = Find-Entity $registry $Id
        if (-not $entity) { throw "Unknown entity: $Id" }
        $manifest = Read-Manifest $entity.id
        [ordered]@{ entity=$entity; manifest=$manifest; currentPath=(Get-CurrentPath $entity.id); currentExists=(Test-Path -LiteralPath (Get-CurrentPath $entity.id)) } | ConvertTo-Json -Depth 10
        if (Test-Path -LiteralPath (Get-CurrentPath $entity.id)) { [IO.File]::ReadAllText((Get-CurrentPath $entity.id),[Text.Encoding]::UTF8) }
    }
    'list' {
        $registry = Read-Registry
        $rows = foreach ($entity in @($registry.entities | Sort-Object id)) {
            $manifest = Read-Manifest $entity.id
            [ordered]@{ id=$entity.id; name=$entity.name; type=$entity.type; revision=$manifest.currentRevision; status=$manifest.status; updatedAt=$manifest.updatedAt; aliases=@($entity.aliases); anchors=@($entity.anchors) }
        }
        @($rows) | ConvertTo-Json -Depth 8
    }
    'commit' {
        $content = Get-FullSafePath $ContentPath
        if (-not (Test-Path -LiteralPath $content -PathType Leaf)) { throw "Content file not found: $content" }
        $lock = Acquire-Lock $Id
        try { Add-ContentRevision (Normalize-Id $Id) ([IO.File]::ReadAllText($content,[Text.Encoding]::UTF8)) $ExpectedRevision $Status | ConvertTo-Json -Depth 8 }
        finally { Release-Lock $lock }
    }
    'import-legacy' {
        $lock = Acquire-Lock $Id
        try { Add-LegacySnapshot (Normalize-Id $Id) $SourcePath | ConvertTo-Json -Depth 8 }
        finally { Release-Lock $lock }
    }
    'finalize-legacy' {
        $source = Get-FullSafePath $SourcePath
        $snapshot = Get-FullSafePath $SnapshotPath
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Legacy source not found: $source" }
        if (-not (Test-Path -LiteralPath $snapshot -PathType Leaf)) { throw "Snapshot not found: $snapshot" }
        if ((Get-Sha256 $source) -ne (Get-Sha256 $snapshot)) { throw 'Source and snapshot hashes do not match; refusing deletion.' }
        $auditOutput = & $PSCommandPath audit -StoreRoot $StoreRoot
        $auditResult = (($auditOutput -join [Environment]::NewLine) | ConvertFrom-Json)
        if (-not $auditResult.ok) { throw "Audit failed; refusing deletion. $auditOutput" }
        Remove-Item -LiteralPath $source -Force
        [ordered]@{ deleted=$source; recoverableFrom=$snapshot; sha256=(Get-Sha256 $snapshot) } | ConvertTo-Json
    }
    'add-alias' {
        $lock = Acquire-Lock 'registry'
        try {
            $registry = Read-Registry
            $entity = Find-Entity $registry $Id
            if (-not $entity) { throw "Unknown entity: $Id" }
            $clean = @($Aliases | Where-Object { $_ } | Select-Object -Unique)
            Assert-IdentityAvailable $registry $clean $entity.id
            $entity.aliases = @(@($entity.aliases) + $clean | Select-Object -Unique)
            Save-Registry $registry
            $entity | ConvertTo-Json -Depth 8
        } finally { Release-Lock $lock }
    }
    'rollback' {
        if ($Revision -lt 1) { throw 'Revision must be at least 1.' }
        $entityId = Normalize-Id $Id
        $match = @(Get-HistoryFiles $entityId | Where-Object { $_.Name -like ('rev-{0:D4}-*' -f $Revision) })
        if ($match.Count -ne 1) { throw "Expected one history file for revision $Revision; found $($match.Count)." }
        $lock = Acquire-Lock $entityId
        try { Add-ContentRevision $entityId ([IO.File]::ReadAllText($match[0].FullName,[Text.Encoding]::UTF8)) $ExpectedRevision 'in-progress' 'rollback' -SkipTemplateValidation | ConvertTo-Json -Depth 8 }
        finally { Release-Lock $lock }
    }
    'merge' {
        if (-not $ConfirmMerge) { throw 'Merge requires -ConfirmMerge after explicit user confirmation.' }
        $sourceEntityId = Normalize-Id $SourceId
        $targetEntityId = Normalize-Id $TargetId
        if ($sourceEntityId -eq $targetEntityId) { throw 'Source and target must differ.' }
        $registryLock = Acquire-Lock 'registry'
        $ids = @($sourceEntityId,$targetEntityId | Sort-Object)
        $firstLock = $null
        $secondLock = $null
        try {
            $firstLock = Acquire-Lock $ids[0]
            $secondLock = Acquire-Lock $ids[1]
            $registry = Read-Registry
            $sourceEntity = Find-Entity $registry $sourceEntityId
            $targetEntity = Find-Entity $registry $targetEntityId
            if (-not $sourceEntity -or -not $targetEntity) { throw 'Source or target entity not found.' }
            $sourceFiles = @(Get-HistoryFiles $sourceEntityId)
            $sourceCurrent = Get-CurrentPath $sourceEntityId
            if (Test-Path -LiteralPath $sourceCurrent) { $sourceFiles += Get-Item -LiteralPath $sourceCurrent }
            foreach ($file in $sourceFiles) {
                $targetManifest = Read-Manifest $targetEntityId
                $newRevision = [int]$targetManifest.currentRevision + 1
                $dest = Get-HistoryPath $targetEntityId $newRevision 'merged'
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $dest
                if ((Get-Sha256 $file.FullName) -ne (Get-Sha256 $dest)) { throw "Merge hash verification failed for $($file.FullName)" }
                $targetManifest.currentRevision = $newRevision
                $targetManifest.updatedAt = [DateTimeOffset]::Now.ToString('o')
                Save-Manifest $targetEntityId $targetManifest
            }
            $targetCurrent = Get-CurrentPath $targetEntityId
            if (-not (Test-Path -LiteralPath $targetCurrent) -and (Test-Path -LiteralPath $sourceCurrent)) {
                Write-Utf8Atomic $targetCurrent ([IO.File]::ReadAllText($sourceCurrent,[Text.Encoding]::UTF8))
            }
            if (-not (Test-Path -LiteralPath $targetCurrent)) { throw 'Neither merge target nor source has a current record.' }
            $targetManifest = Read-Manifest $targetEntityId
            Add-ContentRevision $targetEntityId ([IO.File]::ReadAllText($targetCurrent,[Text.Encoding]::UTF8)) ([int]$targetManifest.currentRevision) $targetManifest.status 'merge' -SkipTemplateValidation | Out-Null
            $targetEntity.aliases = @(@($targetEntity.aliases) + @($sourceEntity.id,$sourceEntity.name) + @($sourceEntity.aliases) | Where-Object { $_ } | Select-Object -Unique)
            $targetEntity.anchors = @(@($targetEntity.anchors) + @($sourceEntity.anchors) | Where-Object { $_ } | Select-Object -Unique)
            $registry.entities = @($registry.entities | Where-Object { $_.id -ne $sourceEntityId })
            Save-Registry $registry
            Remove-Item -LiteralPath (Get-EntityDir $sourceEntityId) -Recurse -Force
            Enforce-HistoryLimit $targetEntityId
            [ordered]@{ source=$sourceEntityId; target=$targetEntityId; sourceRemoved=$true; targetRevision=(Read-Manifest $targetEntityId).currentRevision } | ConvertTo-Json
        } finally {
            Release-Lock $secondLock
            Release-Lock $firstLock
            Release-Lock $registryLock
        }
    }
    'audit' {
        $registry = Read-Registry
        $issues = New-Object System.Collections.Generic.List[string]
        $seen = @{}
        foreach ($entity in @($registry.entities)) {
            foreach ($value in @($entity.id,$entity.name) + @($entity.aliases) + @($entity.anchors)) {
                if (-not $value) { continue }
                $key = $value.ToString().ToLowerInvariant()
                if ($seen.ContainsKey($key) -and $seen[$key] -ne $entity.id) { $issues.Add("Duplicate identity '$value': $($seen[$key]), $($entity.id)") }
                else { $seen[$key] = $entity.id }
            }
            try {
                $manifest = Read-Manifest $entity.id
                $history = @(Get-HistoryFiles $entity.id)
                if ($history.Count -gt $script:HistoryLimit) { $issues.Add("History limit exceeded for $($entity.id): $($history.Count)") }
                $current = Get-CurrentPath $entity.id
                if ([int]$manifest.currentRevision -gt 0 -and -not (Test-Path -LiteralPath $current) -and $manifest.status -ne 'migrated') { $issues.Add("Current file missing for $($entity.id)") }
                if (Test-Path -LiteralPath $current) {
                    $hash = Get-Sha256 $current
                    if ($manifest.currentSha256 -and $hash -ne $manifest.currentSha256) { $issues.Add("Current hash mismatch for $($entity.id)") }
                    $currentHistory = @($history | Where-Object { $_.Name -like ('rev-{0:D4}-*' -f [int]$manifest.currentRevision) })
                    if ($currentHistory.Count -ne 1) { $issues.Add("Current revision history missing or duplicated for $($entity.id): $($manifest.currentRevision)") }
                    elseif ((Get-Sha256 $currentHistory[0].FullName) -ne $hash) { $issues.Add("Current/history content mismatch for $($entity.id): $($manifest.currentRevision)") }
                }
            } catch { $issues.Add($_.Exception.Message) }
        }
        $locks = @(Get-ChildItem -LiteralPath $LocksRoot -Directory -Filter '*.lock' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
        if ($locks.Count -gt 0) { foreach ($item in $locks) { $issues.Add("Active or stale lock: $item") } }
        $result = [ordered]@{ ok=($issues.Count -eq 0); entityCount=@($registry.entities).Count; issues=@($issues); storeRoot=$StoreRoot }
        $result | ConvertTo-Json -Depth 8
        if ($issues.Count -gt 0) { exit 2 }
    }
    'unlock' {
        if (-not $ConfirmUnlock) { throw 'Unlock requires -ConfirmUnlock after checking no writer is active.' }
        $lockPath = Join-Path $LocksRoot ((Normalize-Id $Id) + '.lock')
        if (Test-Path -LiteralPath $lockPath) { Remove-Item -LiteralPath $lockPath -Recurse -Force }
        [ordered]@{ unlocked=$lockPath } | ConvertTo-Json
    }
}
