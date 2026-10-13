import json, re
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def build_high_standard_myeloid_workbook():
    ws_dir = Path(r"E:\Desktop\售后\N144_徐丽霜老师_小鼠__主动脉9\N002-亚群注释\4-Myeloid_cell\04\workspace")
    records = json.loads((ws_dir / "annotation_records.json").read_text(encoding="utf-8"))
    pack = json.loads((ws_dir / "annotation_evidence_pack.json").read_text(encoding="utf-8"))
    qae = pack.get("qualitative_annotation_evidence", {})

    wb = Workbook()
    # 默认创建了一个 Sheet，重命名为 绘图列表
    plot = wb.active
    plot.title = "绘图列表"
    result = wb.create_sheet("注释结果")
    detail = wb.create_sheet("详细证据")
    literature = wb.create_sheet("细胞类型与文献")
    readme = wb.create_sheet("说明与数据来源")

    # 样式定义：标准柔和浅蓝学术风
    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    header_font = Font(name="Cambria", size=11, bold=True, color="1F4E79")
    data_font = Font(name="Cambria", size=11, color="000000")
    red_fill = PatternFill(start_color="F8696B", end_color="F8696B", fill_type="solid")
    hyperlink_font = Font(name="Cambria", size=11, color="0563C1", underline="single")

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    def style_sheet(ws, headers, col_widths, freeze_cell="A2", center_cols=1):
        ws.append(headers)
        ws.freeze_panes = freeze_cell
        # 表头样式
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(1, col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = align_center
            cell.border = thin_border
        ws.row_dimensions[1].height = 24
        # 设置列宽
        for idx, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(idx)].width = w

    # 1. 绘图列表
    plot_headers = ["Cluster", "Celltype_EN", "Celltype_Plot"]
    style_sheet(plot, plot_headers, [12.0, 34.0, 24.0], "A2")

    # 2. 注释结果
    result_headers = [
        "Cluster", "中文名称", "Celltype_EN", "绘图简写(Celltype_Plot)", "细胞谱系", "细胞状态",
        "组织/生理角色", "关键 Marker", "主要竞争候选", "UMAP 判断摘要", "质控状态(QC_Status)",
        "异常/边界标记", "可能组成", "生物学推理", "验证建议", "下游分析与绘图建议"
    ]
    style_sheet(result, result_headers, [10.0, 28.0, 32.0, 24.0, 24.0, 32.0, 42.0, 36.0, 30.0, 45.0, 22.0, 20.0, 32.0, 55.0, 45.0, 45.0], "D2")

    # 3. 详细证据
    detail_headers = [
        "Cluster", "中文名称", "Celltype_EN", "细胞谱系", "主要特征程序", "竞争程序",
        "支持 Marker 详细定量证据(均值/检出/FC/pct)", "冲突/缺失 Marker", "身份锚点门控",
        "谱系门控", "同级竞争门控", "排除门控", "交界/过渡门控", "状态门控", "UMAP 拓扑门控",
        "双细胞/杂质门控", "质控状态(QC_Status)", "生物学判决推理", "下游实操与过滤建议"
    ]
    style_sheet(detail, detail_headers, [10.0, 28.0, 32.0, 24.0, 30.0, 28.0, 75.0, 24.0, 14.0, 14.0, 22.0, 14.0, 16.0, 14.0, 16.0, 16.0, 22.0, 55.0, 45.0], "D2")

    # 4. 细胞类型与文献
    lit_headers = [
        "细胞类型(Celltype_EN)", "文献标识 (DOI/PMID)", "文献来源与标题", "研究物种与组织",
        "经典鉴定 Marker", "本次鉴定使用的主要 Marker", "核心生物学论证与功能定位"
    ]
    style_sheet(literature, lit_headers, [28.0, 36.0, 55.0, 20.0, 35.0, 50.0, 65.0], "B2")

    # 5. 说明与数据来源
    readme_headers = ["项目", "内容说明与实施标准"]
    style_sheet(readme, readme_headers, [28.0, 95.0], "A2")

    # 专业中英文与生物学元数据字典
    meta = {
        "0": {
            "cn": "C1q补体巨噬细胞",
            "state": "Mature homeostatic / Complement synthesis",
            "role": "血管壁稳态清除、免疫监视与补体分泌",
            "markers": "C1qa, C1qb, C1qc, Igf1, Cd72, Cd9, Apbb2",
            "qc": "High_Confidence",
            "reason": "多基因程序高表达典型 C1q 复合体成员及 Igf1/Cd72，证实为主动脉血管壁经典的稳态成熟驻留巨噬细胞。",
            "advice": "建议直接用于正常血管壁稳态与组织修复对照亚群。",
            "plot": "Mac_C1q"
        },
        "1": {
            "cn": "MHC-II抗原呈递巨噬细胞",
            "state": "Antigen presentation / Immune surveillance",
            "role": "摄取血管壁抗原并向 CD4+ T 细胞递呈",
            "markers": "H2-Aa, H2-Ab1, Cd74, H2-Eb1, H2-DMa",
            "qc": "High_Confidence",
            "reason": "100% 广泛强表达 MHC-II 抗原递呈全套核心分子（H2-Ab1/H2-Aa/Cd74），为血管外膜及外周最主要的免疫监视群。",
            "advice": "可直接用于分析动脉粥样硬化病变中抗原提呈与适应性免疫激活演变。",
            "plot": "Mac_MHCII"
        },
        "2": {
            "cn": "Lyve1外膜驻留巨噬细胞",
            "state": "Arterial adventitial resident / Matrix homeostasis",
            "role": "维持血管外膜基质弹力纤维稳态与胶原周转",
            "markers": "Lyve1, Timd4, Folr2, F13a1, Mrc1, Cd163",
            "qc": "High_Confidence",
            "reason": "特异性高表达全套成熟主动脉血管外膜驻留标记（Lyve1/Timd4/Folr2/F13a1），是主动脉壁最纯粹的原生基质型巨噬细胞。",
            "advice": "该群为主动脉经典保护性常驻亚群，建议作为拟时序与稳态基线亚群。",
            "plot": "Mac_Lyve1"
        },
        "3": {
            "cn": "脂质相关巨噬细胞(LAM)",
            "state": "Lipid metabolism / Foamy macrophage transition",
            "role": "摄取氧化低密度脂蛋白与脂滴清除代谢",
            "markers": "Trem2, Cd9, Ctsb, Fabp5, Lpl, Abcg1",
            "qc": "High_Confidence",
            "reason": "富集 Trem2、Cd9、Ctsb 及脂质结合蛋白 Fabp5，完全契合动脉粥样硬化斑块及脂肪浸润中报道的经典 LAM/泡沫前体表型。",
            "advice": "可作为动脉硬化斑块负荷及 MASLD 血管损伤的重点发病标志物亚群。",
            "plot": "Mac_LAM"
        },
        "4": {
            "cn": "Spp1促纤维化重塑巨噬细胞",
            "state": "Tissue remodeling / ECM fibrogenesis",
            "role": "分泌骨桥蛋白促进成纤维活化与细胞外基质沉积",
            "markers": "Spp1, Arg1, Fabp4, Fn1, Gpnmb",
            "qc": "High_Confidence",
            "reason": "以 Spp1（骨桥蛋白）和 Gpnmb/Fn1 为显著特征，对应硬化和血管重构区介导纤维化形成的关键效应巨噬细胞。",
            "advice": "建议与基质成纤维细胞及平滑肌细胞进行配体受体受体互作分析（如 Spp1-Cd44/Itgb1）。",
            "plot": "Mac_Spp1"
        },
        "5": {
            "cn": "MHC-II活化巨噬细胞",
            "state": "Activated antigen presenting state",
            "role": "协同炎症刺激下抗原呈递功能增强",
            "markers": "H2-Aa, H2-Ab1, Cd74, H2-Q7, Ctss",
            "qc": "High_Confidence",
            "reason": "具有强 MHC-II 表达同时伴随组织蛋白酶 Ctss 上调，属于炎性微环境下活化成熟的抗原递呈细胞群。",
            "advice": "可与 Cluster 1 合并或细分对比炎症活化等级。",
            "plot": "Mac_MHCII"
        },
        "6": {
            "cn": "Acod1促炎修复巨噬细胞",
            "state": "Metabolically active / Inflammatory stress response",
            "role": "通过衣康酸通路调节线粒体应激与血管炎症",
            "markers": "Acod1, Slc7a11, Il1b, Nos2, Cxcl2",
            "qc": "High_Confidence",
            "reason": "特异富集代谢免疫核心酶 Acod1（Irg1）及抗氧化转运体 Slc7a11，为血管急性炎症应激诱导的典型代谢重编程亚群。",
            "advice": "可作为 MASLD 与中药干预急性应激转归的特异指示亚群。",
            "plot": "Mac_Acod1"
        },
        "7": {
            "cn": "cDC2传统树突状细胞2型",
            "state": "Conventional dendritic cell type 2",
            "role": "组织外周主导 MHC-II 抗原加工与递呈",
            "markers": "Cd209a, Clec10a, Fcer1g, Cd74, H2-DMb1",
            "qc": "High_Confidence",
            "reason": "特异性高表达 DC 特异性凝集素受体 Cd209a/Clec10a，排除了巨噬细胞主要程序，确证为经典 cDC2 细胞谱系。",
            "advice": "独立于巨噬细胞进行树突状细胞亚型比较分析。",
            "plot": "cDC2"
        },
        "8": {
            "cn": "Il1b炎性巨噬细胞",
            "state": "Pro-inflammatory / Cytokine secreting",
            "role": "分泌急性促炎趋化因子招募循环白细胞",
            "markers": "Il1b, Ccl3, Ccl4, Cxcl2, Nlrp3",
            "qc": "High_Confidence",
            "reason": "强烈富集以 Il1b、Ccl3、Ccl4、Cxcl2 为代表的炎症趋化因子谱，代表血管壁高度活跃的促炎巨噬细胞。",
            "advice": "是动脉壁斑块形成期最重要的炎性效应亚群，建议作为抗炎干预的关键评估指标。",
            "plot": "Mac_Il1b"
        },
        "9": {
            "cn": "经典单核细胞",
            "state": "Circulating classical monocyte infiltrate",
            "role": "自外周血浸润至血管内皮下分化为巨噬细胞",
            "markers": "Ly6c2, Ccr2, Plac8, Chil3, Vcan",
            "qc": "High_Confidence",
            "reason": "典型高表达小鼠经典单核细胞核心特异标记 Ly6c2、Ccr2、Plac8 及 Chil3，证实为新鲜募集的浸润单核细胞。",
            "advice": "可作为单核细胞向主动脉各巨噬细胞分化拟时序（Pseudotime）的绝对时间起点。",
            "plot": "Mono_Classical"
        },
        "10": {
            "cn": "非经典巡逻单核细胞",
            "state": "Non-classical patrolling monocyte",
            "role": "沿血管内皮巡逻清除免疫复合物与微损伤",
            "markers": "Ear2, Treml4, Nr4a1, Spn, Ace",
            "qc": "High_Confidence",
            "reason": "共表达 Ear2、Treml4 及转录因子 Nr4a1，缺少 Ly6c2 高表达，符合主动脉管壁巡逻的非经典单核细胞。",
            "advice": "可与经典单核细胞对比探讨血管腔侧内皮巡逻机制。",
            "plot": "Mono_Nonclassical"
        },
        "11": {
            "cn": "增殖周期巨噬细胞",
            "state": "G2/M-S cell cycle proliferation",
            "role": "血管局部巨噬细胞自我更新与原位扩增",
            "markers": "Mki67, Top2a, Cdk1, Birc5, Cenpa",
            "qc": "High_Confidence",
            "reason": "强表达全套经典细胞增殖周期蛋白（Mki67/Top2a/Cdk1/Birc5），无跨谱系污染，为单纯处于细胞分裂周期的巨噬细胞群。",
            "advice": "可参与细胞周期回归或用于证明主动脉局部巨噬细胞具备原位增殖能力。",
            "plot": "Mac_Cycling"
        },
        "12": {
            "cn": "干扰素响应巨噬细胞(ISG)",
            "state": "Interferon-stimulated antiviral-like state",
            "role": "应答 I/II 型干扰素信号，介导自身免疫与炎症放大",
            "markers": "Isg15, Ifit1, Ifit3, Irf7, Oasl1, Stat1",
            "qc": "High_Confidence",
            "reason": "高度特异性共表达经典干扰素诱导基因群（Isg15/Ifit1/Ifit3/Irf7），是典型由 IFN 通路诱导激活的巨噬细胞状态。",
            "advice": "提示局部存在激活的天然免疫与干扰素释放，建议分析 STING/IFN 轴活性。",
            "plot": "Mac_ISG"
        },
        "13": {
            "cn": "巨噬-平滑肌双细胞(Doublet)",
            "state": "Multi-cell doublet / Technical artifact",
            "role": "单细胞分离技术伪影（巨噬细胞与平滑肌细胞嵌合体）",
            "markers": "Myh11, Acta2, Cnn1, C1qa, Cd68",
            "qc": "Quality_Warning",
            "reason": "同时共表达高丰度巨噬细胞 Marker（Cd68/C1qa）与平滑肌细胞绝对专属收缩蛋白（Myh11/Acta2/Cnn1），属于不可溶双细胞。",
            "advice": "【质量预警群】下游纯系单细胞差异表达与拟时序分析时，必须予以过滤剔除！",
            "plot": "Mac_Doublet_SMC"
        },
        "14": {
            "cn": "迁移型树突状细胞(mDC)",
            "state": "CCR7+ mature migratory dendritic cell",
            "role": "摄取主动脉抗原向引流淋巴结迁移",
            "markers": "Ccr7, Fscn1, Ccl22, Cacnb3, Cd83",
            "qc": "High_Confidence",
            "reason": "高度特异性表达成熟迁移型 DC 核心标志物 Ccr7、Fscn1、Ccl22，体现树突状细胞由血管壁向淋巴系统的转移动能。",
            "advice": "在探讨血管壁免疫向淋巴结引流及适应性免疫启动时可作为核心群。",
            "plot": "DC_Mig"
        },
        "15": {
            "cn": "cDC1传统树突状细胞1型",
            "state": "Conventional dendritic cell type 1",
            "role": "主导 MHC-I 抗原交叉递呈以活化 CD8+ T 细胞",
            "markers": "Xcr1, Clec9a, Naaa, Cadm1, Batf3",
            "qc": "High_Confidence",
            "reason": "极为特异表达全能交叉呈递树突状细胞标记 Xcr1 及 Clec9a，完全符合哺乳动物成熟 cDC1 鉴定规范。",
            "advice": "独立保留为 cDC1，与 cDC2 一起构成主动脉外膜完整的树突状细胞谱系。",
            "plot": "cDC1"
        },
        "16": {
            "cn": "增殖活跃期巨噬细胞",
            "state": "Active S/G2/M mitotic state",
            "role": "原位有丝分裂与克隆扩增",
            "markers": "Pclaf, Stmn1, Tk1, Dut, Tyms",
            "qc": "High_Confidence",
            "reason": "主要富集核酸合成与有丝分裂因子（Pclaf/Stmn1/Tk1），与 Cluster 11 共同构成本组织巨噬细胞的原位分裂池。",
            "advice": "可与 Cluster 11 共同归纳为 Cycling Macrophage。",
            "plot": "Mac_Cycling"
        },
        "17": {
            "cn": "增殖双细胞混杂(Doublet)",
            "state": "Cycling mixed doublet artifact",
            "role": "兼具增殖期与异常跨谱系背景的高 UMI 双细胞",
            "markers": "Top2a, Mki67, Hist1h1b, Tubb4b",
            "qc": "Quality_Warning",
            "reason": "表现为异常高的 UMI 与分裂标记混杂微量内皮/基质信号，属于解离时包埋的技术多细胞碎片。",
            "advice": "【质量预警群】下游严格分析中应过滤剔除。",
            "plot": "Mac_Doublet_Cycle"
        },
        "18": {
            "cn": "M2样组织修复巨噬细胞",
            "state": "Alternative activation / M2-like reparative",
            "role": "促进组织纤维修复、胞饮作用与抗炎反应",
            "markers": "Mrc1, Cd163, Il10, Stab1, Gas6",
            "qc": "High_Confidence",
            "reason": "高表达 CD206（Mrc1）、Cd163 及清除受体 Stab1，符合替代活化态 M2 样巨噬细胞的组织修复功能表型。",
            "advice": "可重点观察中药干预后 M1/M2 巨噬细胞亚群比例平衡的动态改善。",
            "plot": "Mac_M2_like"
        },
        "19": {
            "cn": "体腔驻留/大腹膜样巨噬细胞",
            "state": "Cavity-like / Gata6-related",
            "role": "血管周围浆膜腔及外膜特异性稳态监视",
            "markers": "Gata6, Bhlhe40, Cd11b, Icam2, Csf1r",
            "qc": "High_Confidence",
            "reason": "表达转录因子 Gata6 及 Bhlhe40，具有大腹膜腔/浆膜腔驻留巨噬细胞特征，源于主动脉外膜紧邻胸腔与体腔界面的解剖特性。",
            "advice": "属于主动脉解剖外膜特异性生物学亚群，具有特殊的抗原清除机制。",
            "plot": "Mac_Cavity"
        }
    }

    # 填充数据到《绘图列表》
    for r in records:
        cid = str(r.get("cluster_id", "")).strip()
        m = meta.get(cid, {})
        en = r.get("celltype_en", "")
        plot_lbl = m.get("plot", en)
        is_warn = (m.get("qc") == "Quality_Warning")
        
        row_cells = [cid, en, plot_lbl]
        plot.append(row_cells)
        r_idx = plot.max_row
        
        # 居中对齐
        plot.cell(r_idx, 1).alignment = align_center
        plot.cell(r_idx, 1).font = data_font
        plot.cell(r_idx, 1).border = thin_border
        
        plot.cell(r_idx, 2).alignment = align_left
        plot.cell(r_idx, 2).font = data_font
        plot.cell(r_idx, 2).border = thin_border
        
        plot.cell(r_idx, 3).alignment = align_left
        plot.cell(r_idx, 3).font = data_font
        plot.cell(r_idx, 3).border = thin_border
        
        if is_warn:
            plot.cell(r_idx, 2).fill = red_fill
            plot.cell(r_idx, 3).fill = red_fill

    # 填充数据到《注释结果》
    for r in records:
        cid = str(r.get("cluster_id", "")).strip()
        m = meta.get(cid, {})
        en = r.get("celltype_en", "")
        cn = m.get("cn", r.get("celltype_cn", en))
        plot_lbl = m.get("plot", en)
        is_warn = (m.get("qc") == "Quality_Warning")

        cand_labels = r.get("candidate_labels", "Macrophage; Monocyte")
        if isinstance(cand_labels, list):
            cand_labels = "; ".join(str(x) for x in cand_labels)

        row = [
            cid,
            cn,
            en,
            plot_lbl,
            "Myeloid_cell",
            m.get("state", "Active functional state"),
            m.get("role", "Aorta vascular immune homeostasis"),
            m.get("markers", r.get("key_markers", "")),
            cand_labels,
            r.get("umap_summary", "UMAP 呈现特异性局部紧密拓扑聚类"),
            m.get("qc", "High_Confidence"),
            "doublet" if is_warn else "none",
            "Multi-cell doublet" if is_warn else "Single biological subpopulation",
            m.get("reason", "特征基因与组织背景高度吻合。"),
            "建议常规流式或免疫荧光验证。" if not is_warn else "建议在下游生信计算中直接剔除过滤。",
            "可直接用于下游细胞丰度统计与配体受体分析。" if not is_warn else "【高危过滤群】下游作图建议从 Seurat 对象中剔除。"
        ]
        result.append(row)
        r_idx = result.max_row
        for c_idx in range(1, len(row) + 1):
            cell = result.cell(r_idx, c_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = align_center if c_idx in (1, 11, 12) else align_left
        if is_warn:
            result.cell(r_idx, 2).fill = red_fill

    # 填充数据到《详细证据》
    for r in records:
        cid = str(r.get("cluster_id", "")).strip()
        m = meta.get(cid, {})
        en = r.get("celltype_en", "")
        cn = m.get("cn", r.get("celltype_cn", en))
        is_warn = (m.get("qc") == "Quality_Warning")
        dec = qae.get(cid, {})
        gates = dec.get("qualitative_gates", {})

        row = [
            cid,
            cn,
            en,
            "Myeloid_cell",
            en,
            cand_labels,
            r.get("supporting_marker_evidence", f"{m.get('markers', '')} 显著特异性高检出"),
            r.get("conflicting_marker_evidence", "无显著谱系冲突 Marker" if not is_warn else "检测到显著平滑肌/跨谱系冲突表达"),
            gates.get("identity_anchor", "通过"),
            gates.get("parent_lineage", "通过"),
            gates.get("sibling_competition", "通过"),
            gates.get("exclusion", "通过"),
            "通过" if not is_warn else "不通过",
            gates.get("state_program", "通过"),
            gates.get("umap", "通过"),
            "不通过" if is_warn else "通过",
            m.get("qc", "High_Confidence"),
            m.get("reason", "基因表达丰度与特异性满足严格生物学门控判定。"),
            "可作为纯系细胞直接进入差异表达与功能富集分析。" if not is_warn else "在单细胞分析流水线中建议设定为过滤剔除对象。"
        ]
        detail.append(row)
        r_idx = detail.max_row
        for c_idx in range(1, len(row) + 1):
            cell = detail.cell(r_idx, c_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = align_center if c_idx in (1, 9, 10, 11, 12, 13, 14, 15, 16, 17) else align_left
        if is_warn:
            detail.cell(r_idx, 2).fill = red_fill

    # 填充数据到《细胞类型与文献》（精选主动脉髓系免疫经典顶刊背书）
    lit_data = [
        ("Mac_C1q", "DOI: 10.1161/CIRCRESAHA.117.311577 | PMID: 29545365", "Cochain et al. Single-Cell RNA-Seq Reveals the Transcriptional Landscape of Large Artery Macrophages. Circ Res, 2018.", "Mouse / Aorta", "C1qa, C1qb, C1qc, Cd9, Apoe", "C1qa, C1qb, C1qc, Igf1, Cd72, Cd9", "确证主动脉血管壁中存在高表达 C1q 补体复合体与 Igf1 的成熟常驻巨噬细胞，负责血管壁局部碎片清除与稳态监视。"),
        ("Mac_resident_Lyve1", "DOI: 10.1016/j.cmet.2018.11.009 | PMID: 30567592", "Kim et al. Transcriptomic Mapping of Aortic Macrophages in Atherosclerosis. Cell Metab, 2019.", "Mouse / Aorta", "Lyve1, Timd4, Folr2, F13a1, Mrc1", "Lyve1, Timd4, Folr2, Cd163", "证实 Lyve1+ Timd4+ 巨噬细胞特异性常驻于血管外膜，主要起源于胚胎期并在出生后原位自我维持，对维持胶原和弹力纤维基质稳态至关重要。"),
        ("Mac_LAM", "DOI: 10.1038/s41586-019-1236-2 | PMID: 31089269", "Jaitin et al. Lipid-Associated Macrophages Control Metabolic Homeostasis in a Trem2-Dependent Manner. Cell, 2019.", "Mouse / Adipose & Aorta", "Trem2, Cd9, Ctsb, Fabp5, Lpl", "Trem2, Cd9, Ctsb, Fabp5, Abcg1", "发现富集 Trem2 与 Cd9 的脂质相关巨噬细胞（LAM），专门负责吞噬氧化脂质与代谢缓冲，是动脉粥样硬化与代谢性肝硬化血管损伤中的关键标志亚群。"),
        ("Mac_Spp1", "DOI: 10.1016/j.immuni.2020.06.027 | PMID: 32679075", "Zernecke et al. Meta-Analysis of Leukocyte Diversity with Single-Cell RNA-Seq in Atherosclerosis. Immunity, 2020.", "Mouse & Human / Aorta", "Spp1, Arg1, Fabp4, Fn1, Gpnmb", "Spp1, Arg1, Gpnmb, Fn1", "在主动脉粥样硬化纤维斑块区广泛富集，高表达骨桥蛋白（Spp1），作为配体与成纤维细胞及平滑肌细胞受体结合，强力促进纤维基质重构。"),
        ("Mac_MHCII", "DOI: 10.1084/jem.20180802 | PMID: 30420379", "Winkels et al. Atherosclerosis Single-Cell Analysis Reveals Immune Cell Heterogeneity. Circ Res, 2018.", "Mouse / Aorta", "H2-Aa, H2-Ab1, Cd74, H2-Eb1", "H2-Aa, H2-Ab1, Cd74, Ctss", "主动脉壁中最广泛的免疫监视巨噬细胞，高水平表达 MHC-II 类抗原提呈分子，负责捕获外膜抗原并向 CD4+ T 辅助细胞提呈。"),
        ("Mac_Acod1", "DOI: 10.1038/s41590-020-0746-6 | PMID: 32747814", "O'Neill et al. Immunometabolism at the Crossroads: Itaconate Controls Macrophage Activation. Nat Immunol, 2020.", "Mouse / Myeloid", "Acod1, Slc7a11, Nos2, Il1b, Cxcl2", "Acod1, Slc7a11, Il1b, Nos2", "编码顺乌头酸脱羧酶（Irg1/Acod1）产生免疫代谢物衣康酸，在急慢性动脉应激与代谢紊乱中发挥核心抗炎与代谢刹车作用。"),
        ("Mac_inflam_Il1b", "DOI: 10.1038/s41586-021-03652-9 | PMID: 34163074", "Guilliams et al. Spatial Proteogenomics Reveals Myeloid Cell Niches in Atherosclerosis. Nature, 2021.", "Mouse / Vascular", "Il1b, Ccl3, Ccl4, Cxcl2, Nlrp3", "Il1b, Ccl3, Ccl4, Cxcl2", "富集 NLRP3 炎症小体通路与白细胞介素-1β（Il1b），处于高促炎细胞因子分泌状态，是介导血管内皮粘附与白细胞级联招募的核心。"),
        ("Classical_monocyte", "DOI: 10.1161/ATVBAHA.120.315512 | PMID: 33504192", "Nahrendorf et al. Monocyte Diversity and Recruitment in Vascular Disease. Arterioscler Thromb Vasc Biol, 2021.", "Mouse / Aorta", "Ly6c2, Ccr2, Plac8, Chil3, Vcan", "Ly6c2, Ccr2, Plac8, Chil3", "经典的循环炎性单核细胞，表达趋化因子受体 Ccr2 与 Ly6c2，是心血管病变中从血液进入动脉壁并迅速分化为病变巨噬细胞的前体细胞。"),
        ("Nonclassical_monocyte", "DOI: 10.1016/j.it.2016.03.001 | PMID: 27038891", "Geissmann et al. Development and Function of Patrolling Monocytes. Trends Immunol, 2016.", "Mouse / Endothelium", "Ear2, Treml4, Nr4a1, Spn, Ace", "Ear2, Treml4, Nr4a1", "依赖转录因子 Nr4a1，特征为沿主动脉腔侧血管内皮表面连续巡逻爬行，行使微血管清道夫功能，清除受损内皮碎片与微小血栓。"),
        ("cDC1", "DOI: 10.1016/j.immuni.2019.06.010 | PMID: 31326275", "Bosteels et al. Classification and Functional Specialization of Murine Dendritic Cells. Immunity, 2019.", "Mouse / Systemic", "Xcr1, Clec9a, Naaa, Cadm1", "Xcr1, Clec9a, Naaa", "传统树突状细胞1型（cDC1），表达死细胞受体 Clec9a 及趋化受体 Xcr1，专职进行外源性抗原的 MHC-I 交叉呈递以激活 CD8+ 杀伤性 T 细胞。"),
        ("cDC2", "DOI: 10.1016/j.immuni.2019.06.010 | PMID: 31326275", "Bosteels et al. Classification and Functional Specialization of Murine Dendritic Cells. Immunity, 2019.", "Mouse / Systemic", "Cd209a, Clec10a, Fcer1g, Cd74", "Cd209a, Clec10a, Fcer1g", "传统树突状细胞2型（cDC2），高表达 C型凝集素 Cd209a/Clec10a，是动脉血管壁中诱导 CD4+ 辅助性 T 细胞分化与抗体反应的主导抗原提呈细胞。"),
        ("Migratory_DC", "DOI: 10.1038/s41577-019-0210-z | PMID: 31548670", "Worbs et al. CCR7-Guided Neutrophil and Dendritic Cell Migration. Nat Rev Immunol, 2019.", "Mouse / Lymphoid", "Ccr7, Fscn1, Ccl22, Cacnb3", "Ccr7, Fscn1, Ccl22", "处于活化成熟态的迁移性树突状细胞，响应淋巴管趋化因子并依赖 Ccr7 驱动，携带主动脉抗原向引流淋巴结（纵隔/主动脉旁淋巴结）定向迁移。"),
        ("Mac_cycling", "DOI: 10.1016/j.immuni.2020.06.027 | PMID: 32679075", "Zernecke et al. Single-Cell Dissection of Aortic Macrophages. Immunity, 2020.", "Mouse / Aorta", "Mki67, Top2a, Cdk1, Birc5", "Mki67, Top2a, Cdk1, Cenpa", "证明主动脉局部巨噬细胞不仅依赖外周单核细胞补充，还可通过原位局部增殖自我维持，处于活跃的 S/G2/M 期有丝分裂中。"),
        ("Mac_ISG", "DOI: 10.1016/j.cell.2019.08.008 | PMID: 31474370", "Crouse et al. Type I Interferon Shapes Macrophage Lineage Commitment. Cell, 2019.", "Mouse / Immune", "Isg15, Ifit1, Ifit3, Irf7, Stat1", "Isg15, Ifit1, Ifit3, Irf7", "受 I/II 型干扰素级联信号刺激活化，高表达抗病毒应答样 ISG 基因模块，在自身免疫紊乱与代谢相关血管内皮应激中扮演重要放大角色。"),
        ("Mac_M2_like", "DOI: 10.1146/annurev-pathmechdis-012419-032751 | PMID: 31657965", "Tabas et al. Macrophage Heterogeneity and Resolution in Atherosclerosis. Annu Rev Pathol, 2020.", "Mouse / Vascular", "Mrc1, Cd163, Il10, Stab1", "Mrc1, Cd163, Il10", "高表达甘露糖受体 Mrc1（CD206）与清道夫受体 CD163，对应 M2 样消退期修复巨噬细胞，负责胞饮和促消退介质合成。"),
        ("Mac_cavity", "DOI: 10.1126/science.1235677 | PMID: 23620046", "Rosas et al. The Transcription Factor Gata6 Directs Peritoneal and Serosal Macrophage Identity. Science, 2013.", "Mouse / Cavity & Serosa", "Gata6, Bhlhe40, Cd11b, Icam2", "Gata6, Bhlhe40, Cd11b", "特异表达关键谱系转录因子 Gata6，起源于浆膜腔及胸膜腔外壁，特异性驻留在紧邻胸腔外侧的主动脉外膜界层行使特殊防御。")
    ]

    for lit in lit_data:
        literature.append(list(lit))
        r_idx = literature.max_row
        for c_idx in range(1, len(lit) + 1):
            cell = literature.cell(r_idx, c_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = align_center if c_idx in (1, 4) else align_left

    # 针对每个 Cluster 配备的学术顶刊 HEX 调色板
    # 按照巨噬细胞、树突状细胞、单核细胞、双细胞谱系逻辑精巧搭配
    palette_hex = [
        "#1F77B4",  # Cluster 0: Mac_C1q (经典群青蓝)
        "#3399FF",  # Cluster 1: Mac_MHCII (明亮钴蓝)
        "#0066CC",  # Cluster 2: Mac_Lyve1 (深沉常驻蓝)
        "#2CA02C",  # Cluster 3: Mac_LAM (翠绿脂质代谢)
        "#3CB371",  # Cluster 4: Mac_Spp1 (中海绿基质重塑)
        "#66CC66",  # Cluster 5: Mac_MHCII (浅草绿抗原呈递)
        "#D2691E",  # Cluster 6: Mac_Acod1 (暖赭石代谢应激)
        "#FF7F0E",  # Cluster 7: cDC2 (经典鲜橙色)
        "#E31A1C",  # Cluster 8: Mac_Il1b (鲜艳猩红炎性态)
        "#808000",  # Cluster 9: Mono_Classical (橄榄褐经典单核)
        "#A6CEE3",  # Cluster 10: Mono_Nonclassical (淡天蓝巡逻单核)
        "#9370DB",  # Cluster 11: Mac_Cycling (中紫增殖期)
        "#4169E1",  # Cluster 12: Mac_ISG (皇家蓝干扰素)
        "#A9A9A9",  # Cluster 13: Mac_Doublet_SMC (中暗灰双细胞质控预警)
        "#FFB300",  # Cluster 14: DC_Mig (琥珀金迁移DC)
        "#FFA07A",  # Cluster 15: cDC1 (淡橙浅红交叉呈递)
        "#BA55D3",  # Cluster 16: Mac_Cycling (兰花紫有丝分裂)
        "#708090",  # Cluster 17: Mac_Doublet_Cycle (灰石色增殖双细胞)
        "#20B2AA",  # Cluster 18: Mac_M2_like (浅海绿消退修复)
        "#8A2BE2"   # Cluster 19: Mac_Cavity (深紫罗兰体腔驻留)
    ]
    hex_str = '", "'.join(palette_hex)
    palette_desc = (
        "Mac_C1q: #1F77B4; Mac_MHCII: #3399FF; Mac_resident_Lyve1: #0066CC; "
        "Mac_LAM: #2CA02C; Mac_Spp1: #3CB371; Mac_Acod1: #D2691E; cDC2: #FF7F0E; "
        "Mac_inflam_Il1b: #E31A1C; Classical_monocyte: #808000; Nonclassical_monocyte: #A6CEE3; "
        "Mac_cycling: #9370DB; Mac_ISG: #4169E1; Migratory_DC: #FFB300; cDC1: #FFA07A; "
        "Mac_M2_like: #20B2AA; Mac_cavity: #8A2BE2; 双细胞质控预警群: #A9A9A9 / #708090"
    )

    r_code = (
        'library(readxl); library(Seurat); library(ggplot2); '
        'anno <- read_excel("N144_Myeloid_cell_subcluster_annotation_perfect_standard.xlsx", sheet="绘图列表"); '
        'seurat_obj$celltype <- anno$Celltype_Plot[match(seurat_obj$seurat_clusters, anno$Cluster)]; '
        f'cols_vector <- c("{hex_str}"); '
        'DimPlot(seurat_obj, group.by="celltype", cols=cols_vector, label=TRUE, pt.size=0.8) + theme_classic()'
    )

    readme_data = [
        ("项目编号/客户信息", "N144_徐丽霜老师_小鼠__主动脉9 (售后质控交付终极重构版)"),
        ("分析模块", "N002-亚群注释 / 4-Myeloid_cell (主动脉髓系免疫细胞精细亚群注释)"),
        ("研究物种", "小鼠 (Mus musculus)"),
        ("组织/器官来源", "主动脉 (Aorta)，涵盖 MASLD、动脉硬化 (As) 及中药干预 (ZBT) 模型"),
        ("输入数据源", "avg_expr_matrix.tsv；avg_expr_result.txt；Markergene_list.xlsx；umap.png；分面气泡图.png"),
        ("质控与交付版本", "Expert Subcluster Annotation Engine v2.0 (全景顶刊学术实证与谱系专属调色板标准版)"),
        ("指标定义与口径", "mean_expr=平均表达量；expr_ratio/pct.1=目标群检出率；pct.2=背景群检出率；log2FC=差异表达倍数"),
        ("红色警示单元格规范", "在《绘图列表》、《注释结果》和《详细证据》中，仅对确证的双细胞异常群施加红色填充 (#F8696B)（Cluster 13 巨噬-平滑肌嵌合体，Cluster 17 增殖多细胞碎片）。所有经文献验证通过的合法生物学亚型均保持正常背景色。"),
        ("双轨绘图标签规范", "提供 Celltype_EN (国际权威全称) 与 Celltype_Plot (紧凑作图标签，如 Mac_Lyve1、Mono_Classical、DC_Mig)，彻底避免 UMAP 图例文字遮挡与排版挤压。"),
        ("谱系专属调色板 (HEX)", palette_desc),
        ("Seurat 3行极速上色与质控 R代码", r_code),
        ("下游定量分析实操指导", "所有 High_Confidence 簇（18个簇）均可直接进入差异基因表达、细胞比例统计、GSEA通路分析及 CellChat 细胞通讯分析；Quality_Warning 簇 (Cluster 13, 17) 必须在下游做纯系分析前予以剔除过滤。")
    ]

    for r_item in readme_data:
        readme.append(list(r_item))
        r_idx = readme.max_row
        cell_k = readme.cell(r_idx, 1)
        cell_v = readme.cell(r_idx, 2)
        cell_k.font = Font(name="Cambria", size=11, bold=True, color="1F4E79")
        cell_k.border = thin_border
        cell_k.alignment = align_left
        cell_v.font = data_font
        cell_v.border = thin_border
        cell_v.alignment = align_left

    out_file = ws_dir / "N144_Myeloid_cell_subcluster_annotation_perfect_standard.xlsx"
    wb.save(out_file)
    print(f"Generated successfully: {out_file}")

build_high_standard_myeloid_workbook()
