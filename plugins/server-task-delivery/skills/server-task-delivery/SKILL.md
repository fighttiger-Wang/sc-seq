---
name: server-task-delivery
displayName: D02 · 服务器任务投递 v1.1.0
description: D02 · 服务器任务投递 v1.1.0：基于 SSH 免密密钥连接 110.1.231.2 (openclaw01) 生信计算集群，对指定远程路径或数据（/mnt/test、/mnt/test2）执行秒级目录盘点、Seurat/Monocle/RDS/RData 对象探查、Apptainer 容器化 R/Python 脚本执行、Slurm (allsc/all 分区) 作业投递、状态监控与结果回传。Use when the user specifies a remote server path (e.g. /mnt/test/...), asks to inspect or analyze remote single-cell/spatial data on 110.1.231.2 (openclaw01), or submits/monitors Slurm/Apptainer analysis tasks.
---

# D02 · 服务器任务投递 v1.1.0

面向 `110.1.231.2`（主机名 `openclaw01`）生信计算集群的标准化免密连接、远程目录盘点、RData/RDS 对象快速探查、Apptainer 容器化调用与 Slurm 作业投递规范。

## 一、连接配置与安全红线（SSH Key-Only Protocol）

- **主机/端口/账号**：`110.1.231.2`（SSH 别名 `openclaw01`），端口 `22`，账号 `cloud`
- **认证方式**：强制使用本地 Ed25519 免密密钥 `~/.ssh/id_ed25519`（指纹：`SHA256:kpXGE+KZFjs62yMxMOUbZzm9dJB2IW/oOT4PGsaruxw`）
- **标准调用**：`ssh -o BatchMode=yes -o ConnectTimeout=10 openclaw01 "<remote_command>"`
- **安全红线**：**严禁读取或使用明文密码**；若 `BatchMode=yes` 返回 `Permission denied (publickey...)`，通过 `cmd /c "ssh-keygen -y -P """" -f ~/.ssh/id_ed25519"` 检查私钥口令或 `ssh-agent` 状态，绝不回退密码登录。

## 二、集群存储、Slurm 分区与 Apptainer 路由

- **存储**：`/mnt/test`、`/mnt/test2` 为主/扩展 NFS 数据盘（91 TB）；`/home/cloud` 为 107 GB 系统盘，**严禁将大型 RDS/RData 或中间结果写入 `/` 或 `/tmp`**。
- **Slurm 分区**：主力 `allsc`（`openclaw01~03`，68C/377G）；备选 `all`（`openclaw04`，44C/233G）；`openclaw05` 已 `DOWN`，**严禁 `-w openclaw05`**。
- **Slurm `--mem` 铁律**：`openclaw01` 节点配置了 `RealMemory=1`，**默认严禁在 `#SBATCH` 中显式声明 `--mem=...`**（与 `B05` 规范一致），否则会触发节点配置不可用拒排。
- **Apptainer 首选镜像**：`/mnt/test/FCX/sif/sc_Analysis_V4.0.sif`（配 `APPTAINER_BINDPATH=/mnt/test,/home/cloud`、`R_LIBS_USER=/mnt/test/FCX/Software/lib/R4.4`、`/home/cloud/.local/bin/apptainer`）。
- **按需读取**：完整挂载表、全部 SIF 镜像清单与环境变量见 [references/cluster-and-containers.md](references/cluster-and-containers.md)。

## 三、四大标准作业闭环与避坑守则

配套自动化脚本：[`scripts/remote_bio_runner.ps1`](scripts/remote_bio_runner.ps1)（支持 `-Action list | inspect | probe-rdata | submit-r | status | pull`，默认 `-Mem ""` 省略 `--mem`）。

1. **目录盘点**：严禁在 `/mnt/test/AABB` 等顶层 NFS 跑无保护 `du -sh *`；查看目录用 `ls -la` 或 `find -printf '%s'`。
2. **对象探查**：对未知 `.rData`/`.rds` 先跑 `probe-rdata` 核查对象名、Assays、Reductions 与 `meta.data`。
3. **作业投递**：<2 分钟轻量任务可直连 `apptainer exec`；中重型任务封装 `.sbatch`（UTF-8 无 BOM、LF 换行，不含 `--mem`）投递 `allsc`/`all`，日志放 `<REMOTE_WORKDIR>/logs/`。
4. **避坑与性能**：>5 万细胞拟时序先分层下采样再映射；**严禁覆盖上游原始对象**；Windows 上传脚本需清除 CRLF；单次 SSH 合并执行，简单目录/队列查询可首轮直调免读本文件。

- **按需读取**：四大流程完整命令、`.sbatch` 模板与避坑细节见 [references/workflows-and-examples.md](references/workflows-and-examples.md)。
