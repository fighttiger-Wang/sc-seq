---
name: server-task-delivery
displayName: D02 · 服务器任务投递 v1.1.0
description: D02 · 服务器任务投递 v1.1.0：基于 SSH 免密密钥连接 110.1.231.2 (openclaw01) 生信计算集群，对指定远程路径或数据（/mnt/test、/mnt/test2）执行秒级目录盘点、Seurat/Monocle/RDS/RData 对象探查、Apptainer 容器化 R/Python 脚本执行、Slurm (allsc/all 分区) 作业投递、状态监控与结果回传。Use when the user specifies a remote server path (e.g. /mnt/test/...), asks to inspect or analyze remote single-cell/spatial data on 110.1.231.2 (openclaw01), or submits/monitors Slurm/Apptainer analysis tasks.
---

# D02 · 服务器任务投递 v1.1.0

面向 `110.1.231.2`（主机名 `openclaw01`）生信计算集群的标准化免密连接、远程目录盘点、RData/RDS 对象快速探查、Apptainer 容器化调用与 Slurm 作业投递规范。用户只需指定远程路径（如 `/mnt/test/AABB/...`）或分析任务，即可直接按本规范自动完成连接、探查、脚本投递与结果回收。

---

## 一、连接配置与安全红线（SSH Key-Only Protocol）

### 1. 标准连接信息
- **主机地址**：`110.1.231.2`（已在 `~/.ssh/config` 配置别名 `openclaw01`）
- **端口**：`22`
- **账号**：`cloud`
- **认证方式**：强制使用本地 Ed25519 免密密钥 `~/.ssh/id_ed25519`（指纹：`SHA256:kpXGE+KZFjs62yMxMOUbZzm9dJB2IW/oOT4PGsaruxw`）
- **标准调用命令**：
  ```powershell
  ssh openclaw01 "<remote_command>"
  # 或显式指定参数：
  ssh -o BatchMode=yes -o ConnectTimeout=10 -p 22 cloud@110.1.231.2 "<remote_command>"
  ```

### 2. 安全红线
- **严禁读取或使用明文密码**：不得读取本地任何密码文本文件，不得在命令行参数、脚本、日志或环境变量中传入明文密码。
- **免密异常自检**：若 `BatchMode=yes` 返回 `Permission denied (publickey...)`，通过 `cmd /c "ssh-keygen -y -P """" -f C:\Users\fight\.ssh\id_ed25519"` 检查私钥是否设置了口令（Passphrase）或 `ssh-agent` 是否未启动，并提示用户解锁，绝不回退到密码登录。

---

## 二、集群硬件、存储挂载与 Slurm 队列拓扑

### 1. 存储挂载规范
| 挂载点 | 类型 | 容量 | 用途与规范 |
| :--- | :--- | :--- | :--- |
| **`/mnt/test`** | NFS (`110.1.1.237:/mnt/data/openclaw`) | 91 TB（余 ~46 TB） | **主生信项目与容器数据盘**（如 `/mnt/test/AABB/`、`/mnt/test/FCX/`、`/mnt/test/RJL/`） |
| **`/mnt/test2`** | NFS (`110.1.1.237:/mnt/data/openclaw02`) | 91 TB（余 ~46 TB） | **扩展数据盘** |
| **`/home/cloud`** | XFS (`/dev/mapper/rl-root`) | 107 GB（余 ~39 GB） | 仅存放轻量配置与小型日志，**严禁将大型 RDS/RData 或中间结果写入 `/` 或 `/tmp`** |

### 2. Slurm 计算节点与分区（Partitions）
| 分区名 | 节点列表 | 单节点规格 | 状态 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **`allsc`** (默认 `*`) | `openclaw01`, `openclaw02`, `openclaw03` | 68 CPUs / ~377 GB RAM | `up` (`idle`/`mix`) | **主力单细胞/空间转录组计算分区**（Seurat、Harmony、Monocle2、Slingshot、CellChat 等） |
| **`all`** | `openclaw04` | 44 CPUs / ~233 GB RAM | `up` (`idle`) | 通用计算与分流并发分区 |
| *(禁用)* | `openclaw05` | 44 CPUs | `DOWN` | 节点离线，**严禁使用 `-w openclaw05` 硬编码指定** |

---

## 三、Apptainer 容器环境与 R/Python 运行时路由

宿主机默认环境（`/usr/bin`）未直接安装全套生信 R/Python 包，**所有 R / Python 分析任务必须通过 Apptainer 容器执行**。

### 1. 容器引擎与必配环境变量
```bash
export APPTAINER_BINDPATH=/mnt/test,/home/cloud
export R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4
APPTAINER=/home/cloud/.local/bin/apptainer
```

### 2. 核心验证可用镜像清单（SIF Images）
| 镜像路径 | 大小 | 运行时与核心包 | 适用模块 |
| :--- | :--- | :--- | :--- |
| **`/mnt/test/FCX/sif/sc_Analysis_V4.0.sif`** | 20 GB | R 4.4 + `R_LIBS_USER` 扩展库（`Seurat`, `monocle`, `slingshot`, `SingleCellExperiment`, `Harmony`, `clusterProfiler`, `ggplot2`, `openxlsx`, `rmarkdown`） | **首选主力镜像**：单细胞质控、降维聚类、大类/亚群注释、Slingshot/Monocle2 拟时序、富集、HTML 报告渲染 |
| `/mnt/test/RSY/sc_Analysis_V4.0.sif` | 19 GB | R 4.4.3 (`Seurat 5.2.1`, `clusterProfiler 4.12.6`, `org.Mm.eg.db`) | 备选标准 Seurat V5 核心镜像 |
| `/mnt/test/RJL/sif/sif/ACGT101_10X_mRNA_4.1.sif` | 5.0 GB | 10X mRNA 标准分析环境（另有 `3.9.sif`、`3.8.sif` 及 `ACGT101_10X_ALL.sif` 29 GB） | 10X 官方产线脚本兼容、Monocle2 经典轨迹绘图 |
| `/mnt/test/codex_runtime/sif/ACGT101_SingleCell_ATAC_9.2.sif` | 34 GB | scATAC-seq (`ArchR`, `Signac`) | 单细胞 ATAC 与多组学分析 |
| `/mnt/test/RJL/sif/sif/ACGT101_Spatial_Metabolomics_v1.2.sif` | 5.5 GB | 空间代谢组环境（另有 `MALDIpy_harmonypy2.0.0.sif` 13 GB） | 空间代谢组学与 MALDI 数据处理 |
| `/mnt/test/RJL/sif/sif/gsea_V1.3.sif` | 1.9 GB | GSEA 专用环境 | GSEA 富集分析 |

---

## 四、四大标准作业闭环（Standard Operating Workflows）

本技能提供配套 PowerShell 自动化脚本 [`scripts/remote_bio_runner.ps1`](scripts/remote_bio_runner.ps1)，也可直接通过 `ssh openclaw01` 组合调用。

### 流程 1：指定路径盘点与结果审计（Fast List & Inspect）
- **场景 A：仅查看某目录下有哪些文件夹/文件（秒级响应 `< 1s`）**
  **严禁在 `/mnt/test/AABB` 等顶层 NFS 目录上附带执行 `du -sh *`**（NFS 遍历海量单细胞小文件极易超过 10 秒导致命令转入后台任务）。直接执行单次元数据列举：
  ```powershell
  ssh -o BatchMode=yes -o ConnectTimeout=10 openclaw01 "ls -la --time-style=long-iso '/mnt/test/AABB'"
  # 或使用配套脚本：
  powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" -Action list -RemotePath "/mnt/test/AABB"
  ```
- **场景 B：单个项目目录深度盘点（Inspect & Audit）**
  当用户指定某个具体项目路径（如 `/mnt/test/AABB/059-孟宏学-头颈癌`）时，执行非破坏性目录扫描（默认跳过耗时的 `du -sh`，仅在需要统计磁盘占用时追加 `-IncludeDiskUsage`，且内置 `timeout 5s` 保护；自动排除 `.magic_move_jobs` 与 `bootstrap`）：
  ```powershell
  powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" -Action inspect -RemotePath "/mnt/test/AABB/059-孟宏学-头颈癌"
  ```
**盘点输出要求**：
1. 关键数据对象（`.rData`、`.rds`、`.h5ad`）路径与字节大小（直接通过 `find -printf '%s'` 秒级获取文件大小，无需 `du`）；
2. 已完成的统计表（`.tsv`、`.xlsx`）、图表（`.pdf`、`.png`）与 HTML 报告清单；
3. 读取核心 `summary.tsv` / `input_audit.tsv` 提取细胞数、基因数、分组及亚群分布。

---

### 流程 2：RData / RDS 对象非破坏性快速探查（Object Probe）
在对任何未知 `.rData` 或 `.rds`（如 `Filter_Basicinfo.rData`、`Plot.rData`）编写下游分析脚本前，必须先探查其内部对象名、类型、Assays、Reductions 与 `meta.data` 字段：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" -Action probe-rdata -RemotePath "/mnt/test/AABB/059-孟宏学-头颈癌/Myeloid/Plot.rData"
```
或直接通过 SSH 执行内联探查：
```bash
ssh openclaw01 'export APPTAINER_BINDPATH=/mnt/test,/home/cloud R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4; /home/cloud/.local/bin/apptainer exec /mnt/test/FCX/sif/sc_Analysis_V4.0.sif Rscript --vanilla -e "
f <- \"/mnt/test/AABB/059-孟宏学-头颈癌/Myeloid/Plot.rData\"
if (grepl(\"\\\\.rds$\", f, ignore.case=TRUE)) { obj <- readRDS(f); cat(\"RDS class:\", class(obj), \"\n\") } else { env <- new.env(); nms <- load(f, envir=env); cat(\"RData objects:\", paste(nms, collapse=\", \"), \"\n\"); for (nm in nms) { x <- env[[nm]]; cat(\"---\", nm, \"class:\", class(x), \"\n\"); if (inherits(x, \"Seurat\")) { cat(\"Cells:\", ncol(x), \"Genes:\", nrow(x), \"\nAssays:\", paste(Assays(x), collapse=\",\"), \"\nReductions:\", paste(Reductions(x), collapse=\",\"), \"\nMeta cols:\", paste(colnames(x@meta.data), collapse=\",\"), \"\n\"); print(table(Idents(x))) } } }
"'
```

---

### 流程 3：容器化分析脚本生成与任务投递（Job Submission）

#### A. 任务分级路由原则
1. **轻量级任务（预计耗时 < 2 分钟，内存 < 16 GB）**：如读取 `meta.data` 汇总、绘制单张已知对象的 FeaturePlot/VlnPlot/BoxPlot、导出表格，可通过 `ssh openclaw01` 直接调用 `apptainer exec` 运行。
2. **中重型计算任务（预计耗时 > 2 分钟，或内存 > 16 GB）**：如大样本 Seurat 重聚类、Harmony 整合、`FindAllMarkers`、`Monocle2` DDRTree 降维、`Slingshot` 全量拟合、`CellChat`、`inferCNV` 等，**一律封装为 `.sbatch` 脚本投递至 Slurm（`allsc` 或 `all` 分区）后台运行**，或写入带 `PID` 记录的 `nohup` 任务。

#### B. 标准目录与脚本组织规范
在目标分析目录 `<REMOTE_WORKDIR>` 下统一建立：
- `<REMOTE_WORKDIR>/codex_scripts/`：存放 `.R` / `.py` 核心分析脚本与 `.sbatch` / `.sh` 启动脚本（所有脚本强制 **UTF-8 无 BOM、LF 换行**）；
- `<REMOTE_WORKDIR>/logs/`：存放运行日志與 Slurm 输出（`%x_%j.out`、`%x_%j.err`）；
- `<REMOTE_WORKDIR>/plots/`、`tables/`、`rds/`、`report/`：分类存放正式产出物。

#### C. 标准 Slurm `.sbatch` 投递模板
```bash
#!/usr/bin/env bash
#SBATCH -p allsc
#SBATCH --job-name=sc_task
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=<REMOTE_WORKDIR>/logs/%x_%j.out
#SBATCH --error=<REMOTE_WORKDIR>/logs/%x_%j.err
set -euo pipefail

export APPTAINER_BINDPATH=/mnt/test,/home/cloud
export R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4
export OMP_NUM_THREADS=1

echo "[$(date '+%F %T')] HOST=$(hostname) JOB_ID=${SLURM_JOB_ID:-none} PARTITION=${SLURM_JOB_PARTITION:-none}"

/home/cloud/.local/bin/apptainer exec /mnt/test/FCX/sif/sc_Analysis_V4.0.sif \
  Rscript --vanilla "<REMOTE_WORKDIR>/codex_scripts/run_analysis.R"

echo "[$(date '+%F %T')] DONE"
```

可通过配套脚本一键上传本地 R 脚本并投递 Slurm 作业：
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" `
  -Action submit-r `
  -RemotePath "/mnt/test/AABB/059-孟宏学-头颈癌/Myeloid/subcluster_analysis" `
  -LocalScript "path\to\run_analysis.R" `
  -JobName "myeloid_sub" `
  -Cpus 8 `
  -Mem "64G" `
  -Partition "allsc"
```

---

### 流程 4：作业状态监控与结果回传（Monitor & Fetch）

1. **查看队列与运行状态**：
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" -Action status
   ```
   或直接执行：
   ```powershell
   ssh openclaw01 "squeue -u cloud; sacct -u cloud --starttime=$(Get-Date -Format 'yyyy-MM-dd') --format=JobID,JobName%20,Partition,State,ExitCode,Elapsed,MaxRSS"
   ```
2. **拉取远程图表/报告/表格到本地**：
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\Users\fight\.gemini\config\skills\D02-服务器任务投递\scripts\remote_bio_runner.ps1" `
     -Action pull `
     -RemotePath "/mnt/test/AABB/059-孟宏学-头颈癌/T/trajectory_analysis/trajectory_integrated_report/trajectory_integrated_report.html" `
     -LocalPath "E:\Desktop\trajectory_integrated_report.html"
   ```

---

## 五、生信实战避坑与性能守则（Best Practices）

1. **超大规模细胞（> 50,000 cells）拟时序防卡死策略**：
   - 在 10 万+ 细胞上直接运行 `Slingshot` Step 3 主曲线拟合或 `Monocle2` DDRTree 极易耗时数小时甚至内存溢出；
   - **标准解法**：按亚群分层下采样（如 Slingshot 每簇最多 2,000 细胞，Monocle2 每簇最多 1,000 细胞）构建参考骨架，再通过 UMAP 最近邻线段投影（nearest-segment projection）映射回全量细胞。
2. **禁止覆盖原始上游对象**：
   - 上游提供的 `Filter_Basicinfo.rData`、`Plot.rData`、`clustered_spleen_monocle.Rdata` 一律只读引用；
   - 新生成的中间或校正对象写入子目录（如 `rds/adjusted_*.rds`），并输出 `save_status.tsv` 与 `run_summary.tsv` 留痕。
3. **跨平台脚本换行符**：
   - 从 Windows 本地生成并上传到服务器的 `.sh` / `.sbatch` / `.R` 脚本，上传后务必执行 `sed -i 's/\r$//' <script>` 清除 CRLF，防止 `sbatch` 或 `bash` 报 `bad interpreter: /bin/bash^M`。
4. **极速响应与单回合指令合并守则（Latency Optimization）**：
   - **禁止在 NFS 顶层目录跑无保护的 `du -sh *`**：看目录用 `ls -la` 或 `find -maxdepth 1`（`< 1s`）；需要看文件字节大小用 `find -printf '%s %p\n'`；确需统计目录体积必须加 `timeout 5s du -sh`。
   - **单次 SSH 合并执行**：对于明确的目录查看、测试目录清理、日志读取或脚本投递，将“校验 + 执行 + 结果确认”合并在 **单条 SSH 命令（1 次工具调用）** 内完成，避免拆成多次工具调用造成多轮模型推理与终端启动延迟。
   - **首次直接调用**：当用户仅要求查看目录、检查队列状态或删除指定临时文件时，**无需先 `read_file` 读取本 `SKILL.md` 再执行命令**，若已掌握连接参数（`ssh -o BatchMode=yes openclaw01`），可在首轮直接执行或并行调用。
