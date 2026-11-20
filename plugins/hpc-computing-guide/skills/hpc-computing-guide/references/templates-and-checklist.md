## 三、标准代码模板与实战配置

### 1. fastq 4 行结构高灵敏度体检核心 (`fq_check.awk`)
必须放置在任务工作目录下，用于逐行验证 fastq 结构的绝对合规性：
```awk
NR%4==1 && $0!~/^@/ {h++}
NR%4==2 {s=length($0)}
NR%4==3 && $0!~/^\+/ {p++}
NR%4==0 && length($0)!=s {m++}
END {
  if (h==0 && p==0 && m==0) {
    print 1
  } else {
    print 0
    print h+0, p+0, m+0
  }
}
```
- **判定逻辑**：在 Shell 中通过 `[ "$result" = "1" ]` 判定健康；输出包含坏头行、坏加号行或质量长度不匹配时一律判定为损坏。

### 2. 标准 Slurm 转换作业投递头规范
```bash
#!/bin/bash
#SBATCH -p all
#SBATCH -J sra2fastq
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -o convert_%j.log
#SBATCH -e convert_%j.err

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "[$(date '+%F %T')] 运行节点: $(hostname), 核心配置: 8C/64G"
```
> 注：若投递目标为 `openclaw01`（`RealMemory=1`）等特定集群，遵循 `D02` / `B05` 规范省略 `--mem`。

### 3. 多核多并发极速压缩模板 (pigz)
面对数 TB 明文 fastq，禁止单线程 gzip 耗费数天，采用申请 16 核调用 pigz 双并发压缩：
```bash
find fastq -maxdepth 2 -type f \( -name "GSM*_R1.fastq" -o -name "GSM*_R2.fastq" \) | sort | xargs -P 2 -I {} sh -c '
  f="{}"
  echo "[$(date "+%F %T")] 正在压缩: $f ..."
  pigz -p 8 -f "$f" && echo "[$(date "+%F %T")] 压缩成功: ${f}.gz"
'
```

---

## 四、自查巡检速查清单（Checklist）

在编写或运行生信流程脚本前，逐项对齐：
- [ ] 临时目录 `TMP_OUT` 是否避开了 `/tmp` 并指向了可用容量充足的 NFS（如 `/az1/CoSeq_tmp`）？
- [ ] 输出目录是否避开了在 BeeGFS (`/mnt/lcsc`) 上直接连续写入数十 GB 的超长大文件？
- [ ] `fasterq-dump` 线程是否为 `--threads 4`，并显式指定了 `-m 4000MB --temp ...`？
- [ ] 删除指令是否全部写为 `\rm -rf` 避免了 `trash` 别名报错？
- [ ] 是否在合并后设置了 `fq_check.awk` 体验收，确保不会把静默破损文件送入下游？
- [ ] 重负载任务是否已封装为 `#SBATCH -p all` 投递至计算节点，而非在登录机裸跑？
