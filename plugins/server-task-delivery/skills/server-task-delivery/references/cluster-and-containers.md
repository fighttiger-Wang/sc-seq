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
