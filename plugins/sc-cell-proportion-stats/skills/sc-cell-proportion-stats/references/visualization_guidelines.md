# 出版级可视化设计指南 (Visualization Guidelines)

本规范详细记录了经过期刊审美与视觉审校沉淀的两种出版级图表设计标准：

---

## 一、高分动态网格云雨图 (Publication Raincloud Plot)

### 1. 核心形态结构（三位一体微观布局）
每个子图（Subplot）横向划分为三个互不遮挡的视觉通道：
1. **左侧：抖动散点 (Jittered Scatter Points)**
   - 形状：每组对应独立形状（如 WT: 圆形 `o`, Placebo: 方块 `s`, Treatment1: 三角 `^`, Treatment2: 菱形 `D`）。
   - 填充与描边：**镂空透明背景 (`facecolors='none'`) + 组别高饱和度描边 (`linewidth=1.7`)**。
   - 抖动范围：固定随机种子的微量偏移（$-0.25 \sim -0.12$），确保各点清晰可见不粘连。
2. **中间：极简窄箱线图 (Narrow White-Filled Boxplot)**
   - 宽度：`width = 0.10`（精致紧凑，不侵占两侧空间）。
   - 填充：纯白填充 (`facecolor='white'`)，有效截断背景网格线；边框采用该组专属颜色。
   - 异常值：隐藏默认离群点（`showfliers=False`），避免与左侧真实散点重复干扰。
3. **右侧：平滑核密度估计半小提琴 (Smooth KDE Half-Violin)**
   - 算法：`scipy.stats.gaussian_kde(bw_method='silverman')`。
   - 形态：仅绘制向右展开的单侧半小提琴（`fill_betweenx`），透明度 `alpha=0.28`，带精细同色描边。

### 2. 宏观防重叠工程架构 (Isolated Header Row Architecture)
- **痛点**：传统绘图将组图例或显著性说明置于子图内部或自由浮动，当细胞类型数量变化或 Y 轴上限波动时极易发生相互重叠或压住上方连线。
- **解决方案**：
  - 使用 `matplotlib.gridspec.GridSpec(nrows + 1, ncols, height_ratios=[header_h / panel_h] + [1.0] * nrows)`。
  - **第 0 行作为绝对隔离 Header 区**（物理高度固定为 2.0 英寸）：
    - **上层 ($y=0.82$)**：`Experimental Groups` 实验组图例框（水平展开横排）。
    - **下层 ($y=0.22$)**：`Significance Thresholds` 独立灰色圆角信息条（与图例保留 ~1.1 英寸纯白间距）。
  - 下方所有子图从 Row 1 开始绘制，从几何架构上 100% 杜绝元素相互挤压。

### 3. 自适应动态网格 (Dynamic Grid Spec)
- 当细胞类型数量 $N$ 任意变化时：
  - $N \leq 3$：单行排布（$1 \times N$）。
  - $4 \leq N \leq 8$：3 或 4 列（如 6 个细胞类型采用 $2 \times 3$）。
  - $9 \leq N \leq 12$：4 列动态排布（如 10 个为 $3 \times 4$，11 个为 $3 \times 4$）。
  - 末尾未使用的空白子图通过 `ax.axis('off')` 彻底隐藏，保持版面整洁。

---

## 二、多维细胞比例复合气泡图 (Multi-Dimensional Composite Bubble Plot)

参考 *Cancer Cell* / *Nature* 高分文章复合图样式（通过 R 语言 `aplot` 包对齐拼装）：
1. **顶部面板 (Top Panel)**：样本或分组水平的绝对细胞计数堆叠柱状图 (Stacked Barplot)。
2. **中心面板 (Center Panel)**：细胞比例分面气泡图 (Bubble DotPlot)。
   - 气泡大小严格映射细胞占比百分比（`range = c(2.5, 11)`）。
   - 气泡颜色映射细胞大类或精细分型。
3. **右侧面板 (Right Panel)**：各细胞类型在全数据集中的总细胞计数横向条形图 (Horizontal Barplot)。
4. **对齐规范**：通过 `insert_top()` 与 `insert_right()` 强制保证中心点图的坐标系与上下左右条形图在像素级无缝精准对齐。
