param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("status", "list", "inspect", "probe-rdata", "submit-r", "pull")]
    [string]$Action,

    [string]$HostAlias = "openclaw01",
    [string]$RemotePath = "",
    [string]$LocalScript = "",
    [string]$LocalPath = "",
    [string]$JobName = "sc_analysis",
    [int]$Cpus = 8,
    [string]$Mem = "64G",
    [string]$Partition = "allsc",
    [string]$SifImage = "/mnt/test/FCX/sif/sc_Analysis_V4.0.sif",
    [switch]$IncludeDiskUsage
)

$ErrorActionPreference = "Stop"
$SshBaseArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=10", $HostAlias)

function Invoke-RemoteBash {
    param([string]$CommandText)
    $cleanCmd = ($CommandText -replace "`r`n", "`n") + "`n"
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($cleanCmd))
    & ssh @SshBaseArgs "echo '$b64' | base64 -d | bash"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote SSH command failed with exit code $LASTEXITCODE"
    }
}

switch ($Action) {
    "status" {
        $cmd = @"
echo '=== NODE & STORAGE ==='
hostname && uptime
df -hT /mnt/test /mnt/test2 /
echo '=== SLURM PARTITIONS ==='
sinfo
echo '=== ACTIVE JOBS (cloud) ==='
squeue -u cloud
echo '=== RECENT JOBS TODAY ==='
sacct -u cloud --starttime=`$(date +%F) --format=JobID,JobName%22,Partition,NodeList,State,ExitCode,Elapsed,MaxRSS 2>/dev/null || true
"@
        Invoke-RemoteBash $cmd
    }

    "list" {
        if ([string]::IsNullOrWhiteSpace($RemotePath)) {
            throw "-RemotePath is required for Action=list"
        }
        $cmd = @"
set -euo pipefail
TARGET='$RemotePath'
if [ ! -e "`$TARGET" ]; then
    echo "ERROR: Remote path does not exist: `$TARGET" >&2
    exit 2
fi
ls -la --time-style=long-iso "`$TARGET"
"@
        Invoke-RemoteBash $cmd
    }

    "inspect" {
        if ([string]::IsNullOrWhiteSpace($RemotePath)) {
            throw "-RemotePath is required for Action=inspect"
        }
        $duBlock = if ($IncludeDiskUsage) {
            'echo "=== DISK USAGE (5s timeout guard) ==="; timeout 5s du -sh "$TARGET" "$TARGET"/* 2>/dev/null || echo "[WARN] du timed out on NFS; skipped"'
        } else {
            'echo "=== DISK USAGE SKIPPED (pass -IncludeDiskUsage to enable) ==="'
        }
        $cmd = @"
set -euo pipefail
TARGET='$RemotePath'
if [ ! -e "`$TARGET" ]; then
    echo "ERROR: Remote path does not exist: `$TARGET" >&2
    exit 2
fi
$duBlock
echo "=== FILE TREE (excluding .magic_move_jobs & bootstrap) ==="
find "`$TARGET" -maxdepth 3 -not -path '*/.magic_move_jobs*' -not -path '*bootstrap*' -printf '%y %12s %TY-%Tm-%Td %TH:%TM %p\n' | sort -k5
echo "=== SUMMARY / AUDIT PREVIEWS ==="
find "`$TARGET" -maxdepth 3 -type f \( -name "*summary*.tsv" -o -name "*summary*.txt" -o -name "*audit*.tsv" \) -exec head -n 30 {} + 2>/dev/null || true
"@
        Invoke-RemoteBash $cmd
    }

    "probe-rdata" {
        if ([string]::IsNullOrWhiteSpace($RemotePath)) {
            throw "-RemotePath is required for Action=probe-rdata"
        }
        $cmd = @"
set -euo pipefail
export APPTAINER_BINDPATH=/mnt/test,/home/cloud
export R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4
/home/cloud/.local/bin/apptainer exec '$SifImage' Rscript --vanilla -e '
f <- "$RemotePath"
if (!file.exists(f)) stop("File not found: ", f)
cat("Target File:", f, "\nSize (bytes):", file.info(f)[["size"]], "\n\n")
suppressPackageStartupMessages({
  library(Seurat)
  library(monocle)
})
inspect_one <- function(nm, x) {
  cat("========================================\n")
  cat("Object Name:", nm, "| Class:", paste(class(x), collapse=", "), "\n")
  if (inherits(x, "Seurat")) {
    cat("Dimensions:", nrow(x), "genes x", ncol(x), "cells\n")
    cat("Assays:", paste(Assays(x), collapse=", "), "\n")
    cat("Reductions:", paste(Reductions(x), collapse=", "), "\n")
    cat("Metadata columns:", paste(colnames(x@meta.data), collapse=", "), "\n")
    cat("Active Ident summary (top 25):\n")
    print(head(sort(table(Idents(x)), decreasing=TRUE), 25))
    for (col in intersect(c("celltype", "Celltype", "subcelltype", "group", "Group", "seurat_clusters"), colnames(x@meta.data))) {
      cat("\nColumn [", col, "] distribution:\n", sep="")
      print(head(sort(table(x@meta.data[[col]], useNA="ifany"), decreasing=TRUE), 25))
    }
  } else if (inherits(x, "CellDataSet")) {
    cat("Dimensions:", nrow(x), "features x", ncol(x), "cells\n")
    cat("pData columns:", paste(colnames(Biobase::pData(x)), collapse=", "), "\n")
  } else if (is.data.frame(x) || is.matrix(x)) {
    cat("Dimensions:", nrow(x), "rows x", ncol(x), "cols\n")
    print(head(x, 5))
  } else {
    str(x, max.level=1)
  }
}
if (grepl("\\.rds$", f, ignore.case=TRUE)) {
  obj <- readRDS(f)
  inspect_one("RDS_ROOT", obj)
} else {
  env <- new.env()
  nms <- load(f, envir=env)
  cat("Loaded RData objects:", paste(nms, collapse=", "), "\n")
  for (nm in nms) inspect_one(nm, env[[nm]])
}
'
"@
        Invoke-RemoteBash $cmd
    }

    "submit-r" {
        if ([string]::IsNullOrWhiteSpace($RemotePath) -or [string]::IsNullOrWhiteSpace($LocalScript)) {
            throw "-RemotePath (workdir) and -LocalScript are required for Action=submit-r"
        }
        if (-not (Test-Path $LocalScript)) {
            throw "LocalScript not found: $LocalScript"
        }
        $scriptName = Split-Path $LocalScript -Leaf
        $remoteScriptDir = "$RemotePath/codex_scripts"
        $remoteLogDir = "$RemotePath/logs"
        $remoteScriptPath = "$remoteScriptDir/$scriptName"
        $remoteSbatchPath = "$remoteScriptDir/run_${JobName}.sbatch"

        $rawScript = (Get-Content -Raw -Encoding UTF8 $LocalScript) -replace "`r`n", "`n"
        $scriptB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($rawScript))

        $sbatchCmd = @"
set -euo pipefail
mkdir -p '$remoteScriptDir' '$remoteLogDir' '$RemotePath/plots' '$RemotePath/tables' '$RemotePath/rds'
echo '$scriptB64' | base64 -d > '$remoteScriptPath'
cat << 'EOF' > '$remoteSbatchPath'
#!/usr/bin/env bash
#SBATCH -p $Partition
#SBATCH --job-name=$JobName
#SBATCH --cpus-per-task=$Cpus
#SBATCH --mem=$Mem
#SBATCH --time=12:00:00
#SBATCH --output=$remoteLogDir/%x_%j.out
#SBATCH --error=$remoteLogDir/%x_%j.err
set -euo pipefail

export APPTAINER_BINDPATH=/mnt/test,/home/cloud
export R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4
export OMP_NUM_THREADS=1

echo "[`$(date '+%F %T')] HOST=`$(hostname) JOB_ID=`${SLURM_JOB_ID:-none} PARTITION=`${SLURM_JOB_PARTITION:-none}"
/home/cloud/.local/bin/apptainer exec '$SifImage' Rscript --vanilla '$remoteScriptPath'
echo "[`$(date '+%F %T')] COMPLETED"
EOF
chmod +x '$remoteSbatchPath'
sbatch '$remoteSbatchPath'
"@
        Invoke-RemoteBash $sbatchCmd
    }

    "pull" {
        if ([string]::IsNullOrWhiteSpace($RemotePath) -or [string]::IsNullOrWhiteSpace($LocalPath)) {
            throw "-RemotePath and -LocalPath are required for Action=pull"
        }
        $parentDir = Split-Path $LocalPath -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        & scp -r -o BatchMode=yes -o ConnectTimeout=10 "${HostAlias}:${RemotePath}" $LocalPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to pull remote path via scp"
        }
        Write-Host "Successfully pulled ${RemotePath} -> ${LocalPath}"
    }
}
