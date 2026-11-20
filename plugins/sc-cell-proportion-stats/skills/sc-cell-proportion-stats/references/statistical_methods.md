# 统计分析方法与计算规范 (Statistical Methods)

单细胞细胞类型占比的组间统计分析必须兼顾**生物学重复的样本独立性**与**多重假设检验的假阳性控制**。

---

## 1. 样本水平细胞占比计算 (Sample-Level Percentage)

对于样本 $s$ 和细胞类型 $c$：
$$\text{Percentage}_{s, c} = \frac{N_{s, c}}{\sum_{k} N_{s, k}} \times 100\%$$
- 每一个生物学重复样本作为一个独立的观测值单位（避免将单个细胞作为自由度导致过度膨胀）。
- 若某样本中某细胞类型计数为 0，百分比补零（0.0%），确保样本量 $N$ 一致。

---

## 2. 组水平描述性统计量 (Group Descriptive Statistics)

对于每个实验组 $g$ 计算：
- **均值 (Mean)**：$\bar{x} = \frac{1}{n} \sum_{i=1}^n x_i$
- **标准差 (SD)**：$s = \sqrt{\frac{1}{n-1} \sum_{i=1}^n (x_i - \bar{x})^2}$
- **标准误 (SEM)**：$\text{SEM} = \frac{s}{\sqrt{n}}$
- **中位数 (Median)** 与 **四分位距 (IQR)**：$Q_3 - Q_1$，适配非正态偏态分布描述。

---

## 3. 全局多组假设检验 (Global Hypothesis Testing)

当实验分组数 $K \geq 3$ 时：
1. **单因素方差分析 (One-way ANOVA)**：参数检验，评估各组均值是否存在显著总体差异。
2. **Kruskal-Wallis 秩和检验**：非参数检验，对小样本或非正态分布具有强健稳健性。

---

## 4. 两两比较与效应量评估 (Pairwise Contrasts)

对于任意两组 $G_1$ 与 $G_2$：
1. **Welch's 双尾两样本 $t$ 检验 (Welch's t-test)**：不假定两组方差齐性（比 Student's t 检验更稳健）。
2. **Wilcoxon 秩和检验 (Mann-Whitney U)**：非参数两样本秩和检验。
3. **变化倍数与 Log2FC**：
   $$\text{Fold Change} = \frac{\bar{x}_2 + \epsilon}{\bar{x}_1 + \epsilon}, \quad \log_2\text{FC} = \log_2(\text{Fold Change})$$
   （设定伪计数 $\epsilon = 0.001\%$ 防止分母为 0）。
4. **多重检验校正 (FDR / p.adj)**：使用 Benjamini-Hochberg (BH) 算法对全部细胞类型的同一对比进行校正。

---

## 5. 显著性阈值标记规范 (Significance Thresholds)

遵循国际顶级期刊标准：
- `***` : $p < 0.001$（极显著差异）
- `**`  : $p < 0.01$（高度显著差异）
- `*`   : $p < 0.05$（具有统计学显著性）
- `.`   : $p < 0.1$（边缘显著性 / 趋势）
- `ns`  : $p \geq 0.1$（无显著差异）

---

## 6. Ro/e 组织偏好性分析 (Ratio of Observed to Expected Cells)

通过列联表卡方检验评估各细胞类型在不同实验组中的富集或耗竭：
$$\text{Ro/e} = \frac{\text{Observed}}{\text{Expected}}$$
其中期望频数 $\text{Expected}_{i, j} = \frac{R_i \times C_j}{N_{\text{total}}}$：
- $\text{Ro/e} > 1$：该细胞类型在该组中呈**正向偏好/富集**。
- $\text{Ro/e} < 1$：该细胞类型在该组中呈**负向偏好/耗竭**。
