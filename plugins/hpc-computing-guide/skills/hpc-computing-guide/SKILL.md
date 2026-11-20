---
name: hpc-computing-guide
displayName: D01 · HPC超算指南 v1.0.0
description: D01 · HPC超算指南 v1.0.0：基于多轮售后实战沉淀的生信 HPC 集群存储选型、计算调度、I/O 避坑与自动化体检工业级规范。覆盖 BeeGFS 客户端静默丢块、/tmp 根分区爆满打崩进程、fasterq-dump 线程竞争导致 read 质量错位、登录机弱算力 I/O 拥塞（80% wa 假死）、Slurm 动态调度策略、NFS 稳健中转机制与 fastq 4 行结构强制体验收闸门。Use when writing bioinformatics workflow scripts, configuring HPC/Slurm jobs, designing large-scale I/O pipelines, diagnosing cluster I/O bottlenecks or fastq corruption, or running SRA conversion and RNA-seq data processing.
---

# D01 · HPC超算指南 v1.0.0

专属生信 HPC 混合存储集群（BeeGFS 分布式存储 + 多路 NFS 网络挂载 + 极小本地根分区 + Slurm 异构计算节点）的**工业级计算与 I/O 避坑守门规范**。

沉淀自千万级 Reads / TB 级真实售后单细胞外来数据修复实战。彻底杜绝“集群静默丢块数据真坏”、“根分区写满导致命令静默截断”、“工具多线程竞争造成 fastq 序列错位”、“登录机跑重任务拖垮全局”等典型翻车现象。

---

## 一、集群全景架构与三大存储层级（Storage Hierarchy）

在编写任何计算与 I/O 脚本前，必须首先明确集群挂载点的物理特性与致命陷阱：

| 存储层级 | 典型挂载点 | 物理类型 | 特性与容量 | 致命缺陷 / 绝对禁忌 | 正确用途 |
|---|---|---|---|---|---|
| **层级 1：极小系统盘** | `/`, `/tmp`, `/boot` | 本地 XFS (如 `/dev/centos-root`) | **总容量通常极小 (仅 28G，常年余量 < 5G)** | **严禁作任何计算中转与临时文件写入！** `--size-check off` 关闭检查后，满盘会导致数据静默截断或工具异常退出。 | 仅供系统底层运行；可复用工具必须存放在当前工作目录，严禁放 `/tmp`。 |
| **层级 2：分布式存储** | `/mnt/lcsc` 等 | BeeGFS (`beegfs_nodev14`) | 容量巨大 (292T，余 50T+)，吞吐高 | **网络客户端连续大写入或超长 `cat` 追加存在已知静默丢块 Bug！** 工具退出码报 0、文件存在，但内部字节随机丢失，导致 fastq 4 行结构错位。 | **只适合存放最终静态产物、参考基因组与代码脚本**；**严禁直写 fasterq-dump 输出与合并直写！** |
| **层级 3：NFS 网络挂载** | `/az1`, `/qe1`, `/public13` | NFS (`AZ1:/mnt/data`) | 容量适中 (15T，余量 5T~6T 充沛) | 跨网络读写延时略高，但**实测写数十至上百 GB 连续大文件完全稳健、绝不丢块！** | **唯一推荐的计算中转区 (Scratch/TMP_OUT)** 与样本级安全合并区！ |

---

## 二、六大不可逾越的底层避坑铁律（Ironclad Guardrails）

### 1. 【BeeGFS 丢块熔断与 NFS 安全中转铁律】
- **现象**：在 `/mnt/lcsc` (BeeGFS) 上直接运行 `cat srr1.fq srr2.fq > sample.fq`，累计数十至上百 GB 写入后，客户端静默丢失块，退出码仍为 0，但解开后发现 `+` 行或序列缺失 2 行，后续亿级 Reads 整体移位报废。
- **铁律**：
  1. 所有单 SRR 转换的临时输出（`--outdir`）、排序临时目录（`--temp`），**必须配置在 NFS 挂载点**（如 `/az1/CoSeq_tmp`）。
  2. 样本级多文件合并（`cat`）**必须在中转盘上完成**；
  3. 在中转盘上通过 **4 行结构体检闸门（`fq_check.awk` 输出 1）** 确认无误后，再 `mv` 回 BeeGFS 目标目录！

### 2. 【/tmp 根分区物理隔离禁令】
- **现象**：很多生信工具（如 `fasterq-dump`、`sort`、`samtools`）默认将临时文件倾倒至 `/tmp`。而登录节点 `/tmp` 挂载在根分区（仅 28G），大样本处理时瞬间打到 100% 满，触发级联崩溃。
- **铁律**：
  1. 必须在所有工具调用中显式指定临时目录：
     - `fasterq-dump --temp /az1/CoSeq_tmp/fq_${srr}/tmp`
     - `sort -T /az1/CoSeq_tmp`
     - `samtools sort -T /az1/CoSeq_tmp`
  2. 严禁把可执行辅助脚本（如 `fq_check.awk`）放在 `/tmp`，系统定期清理或重启会导致后续脚本全量误判。

### 3. 【fasterq-dump 多线程与排序内存配置规范】
- **现象 1**：fasterq-dump 使用 `--threads 8` 处理单细胞 98bp 长 read 时，存在多线程读写竞争，随机打乱 Read 顺序，造成序列与质量行错位。
- **现象 2**：fasterq-dump 默认排序内存 `-m` 仅有 100MB，遇到千万级 Reads 时疯狂向磁盘刷临时文件，把磁盘打到 80%+ `wa`（I/O 等待），耗时拉长 10 倍以上。
- **铁律**：
  - **线程数强制锁定为 4**：`--threads 4`（实测最兼顾速度与数据一致性，严禁调为 8）；
  - **显式分配排序内存**：`-m 4000MB`（在 64G+ 内存节点上配置 4G 排序内存，IO 吞吐提升 5~8 倍）；
  - **关闭空间预检虚报**：`--size-check off`（避免工具因虚拟盘计算误差直接报 `disk-limit exceeded` 闪退）。

### 4. 【弱算力登录节点禁跑重任务铁律】
- **现象**：集群登录机（如 `person83`）通常为 2 核 3.8G 内存的轻量虚拟机。在此运行大数据量转换或解压，Linux Page Cache 无法支撑，CPU 瞬间飙到 `82.9% wa`，系统近乎假死。
- **铁律**：
  - 登录节点仅允许执行：目录查看、小脚本提交（`sbatch`）、日志监控与轻量预检；
  - 凡涉及 `fasterq-dump`、`pigz`、`bwa`、`CellRanger`、大数据量 `fq_check` 等高负载任务，**必须全部封装为 Slurm 脚本投递到计算节点**！
  - **Slurm 调度原则**：优先投递 `-p all` 分区（动态分配拥有 44~72 核、250G+ 大内存的闲置节点），严禁在脚本中硬编码已宕机节点（如历史写死 `-w node202`）。

### 5. 【系统 alias 与 Shell 脚本绝对兼容铁律】
- **现象**：集群环境通常在全局 profile 中将 `rm` 别名映射为 `trash`。在 Shell 脚本中使用 `rm -f` 会报错：`trash: invalid option -- 'f'`，导致脚本半路中断、临时垃圾堆积。
- **铁律**：
  - 脚本中删除文件/目录**一律使用原生转义命令**：`\rm -rf "$target"` 或 `/bin/rm -rf "$target"`；
  - 换行符与编码：所有 `.sh`、`.awk` 文件必须为 **UTF-8 无 BOM、LF 换行**，严禁包含 `\r`。

### 6. 【双体检闸门与断点续传设计准则】
- 任何批量转换/合并脚本必须内置**两道体检闸门**：
  1. **第一道（per-SRR 级）**：单 SRR 转换完毕后，立即校验提取的 R1/R2 文件，不合格即刻清理并重试（最多重试 3 次）；
  2. **第二道（Sample 级）**：样本合并完毕后，在正式重命名/移动前执行整体结构检验，失败则回滚并保留源文件，绝不让破损文件流入下游。
- **续传防坑**：断点续传检查不得只简单判断“文件是否存在”，必须检查“文件非空且通过体检”，若上次被强制中断，必须先清理残留的半成品临时文件。

---

## 三、标准代码模板与自查清单

- **按需读取**：`fq_check.awk` 4 行结构体检脚本、Slurm 作业投递头模板、`pigz` 多核并发压缩模板及 6 项投递前自查清单，见 [references/templates-and-checklist.md](references/templates-and-checklist.md)。
