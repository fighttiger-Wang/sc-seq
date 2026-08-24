[CmdletBinding()]
param(
  [Parameter()]
  [string]$MarketplaceRoot = $PSScriptRoot,

  [Parameter()]
  [string]$OutputDirectory = (Join-Path $PSScriptRoot 'outputs'),

  [Parameter()]
  [string]$BundleName
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath($MarketplaceRoot).TrimEnd('\')
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
$doctorPath = Join-Path $root 'Test-PersonalSkillMarketplace.ps1'

& $doctorPath -MarketplaceRoot $root
if ($LASTEXITCODE -ne 0) {
  throw 'Marketplace validation failed. Bundle was not created.'
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
if ([string]::IsNullOrWhiteSpace($BundleName)) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $baseName = "personal-codex-skills-$stamp"
}
else {
  if ($BundleName -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') {
    throw 'BundleName must contain only letters, digits, dots, underscores, or hyphens and be at most 80 characters.'
  }
  $baseName = $BundleName
}
$zipPath = Join-Path $outputRoot "$baseName.zip"
$filesHashPath = Join-Path $outputRoot "$baseName.files.sha256"
$zipHashPath = Join-Path $outputRoot "$baseName.zip.sha256"

$excludedPattern = '[\\/](\.git|logs|outputs|tmp|__pycache__|test_debug[^\\/]*)[\\/]'
$files = @(Get-ChildItem -LiteralPath $root -File -Recurse -Force | Where-Object {
    $_.FullName -notmatch $excludedPattern -and
    $_.Extension -notin @('.pyc', '.pyo') -and
    $_.Name -notmatch '(^\.env($|\.)|\.pem$|\.key$|credentials|secrets?)'
  } | Sort-Object FullName)

if ($files.Count -eq 0) {
  throw 'No files were selected for the bundle.'
}

$hashLines = foreach ($file in $files) {
  $relative = $file.FullName.Substring($root.Length).TrimStart('\').Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
Set-Content -LiteralPath $filesHashPath -Value $hashLines -Encoding utf8

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

$stream = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::CreateNew)
try {
  $archive = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
  try {
    foreach ($file in $files) {
      $relative = $file.FullName.Substring($root.Length).TrimStart('\').Replace('\', '/')
      [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $relative, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $filesHashPath, 'bundle-files.sha256', [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
  }
  finally {
    $archive.Dispose()
  }
}
finally {
  $stream.Dispose()
}

$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $zipHashPath -Value "$zipHash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ascii

Write-Host "Bundle: $zipPath"
Write-Host "Files: $($files.Count)"
Write-Host "File manifest: $filesHashPath"
Write-Host "ZIP SHA-256: $zipHashPath"
