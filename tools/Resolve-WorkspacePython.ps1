function Resolve-WorkspacePython {
  param([string]$ExplicitPath, [string]$Root)
  if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
    $resolved = [IO.Path]::GetFullPath($ExplicitPath)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { throw "Python was not found: $resolved" }
    return $resolved
  }
  foreach ($name in @('python', 'python3')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $command -and [string]$command.Source -notmatch '[\\/]WindowsApps[\\/]') { return [string]$command.Source }
  }
  $candidates = [Collections.Generic.List[string]]::new()
  if ($env:CODEX_HOME) { $candidates.Add((Join-Path $env:CODEX_HOME 'runtimes\codex-primary-runtime\dependencies\python\python.exe')) }
  if ($env:USERPROFILE) { $candidates.Add((Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')) }
  $cursor = [IO.DirectoryInfo][IO.Path]::GetFullPath($Root)
  for ($depth = 0; $depth -lt 7 -and $null -ne $cursor; $depth++) {
    $candidates.Add((Join-Path $cursor.FullName 'codex-home\runtimes\codex-primary-runtime\dependencies\python\python.exe'))
    $cursor = $cursor.Parent
  }
  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
  }
  throw 'Python 3.10 or newer could not be located. Install it or pass its full path.'
}
