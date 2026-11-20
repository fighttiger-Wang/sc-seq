#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# Script: plot_dynamic_raincloud.py
# Skill: B05-细胞比例统计图
# Description: Publication-ready Raincloud significance plotting engine with
#   dynamic auto-layout grid and zero-overlap isolated header architecture.
#   Reproduces Nature/Cell high-impact raincloud style:
#     - Left: Hollow jittered scatter points (colored border, group marker)
#     - Middle: Narrow white-filled boxplot
#     - Right: Smooth KDE half-violin
#     - Top: Multi-tiered significance brackets
#     - Dedicated Row 0 Header: Isolated group legend and significance banner
# ==============================================================================

import os
import sys
import argparse
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from scipy.stats import gaussian_kde, ttest_ind, mannwhitneyu

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.linewidth'] = 1.0
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

DEFAULT_PALETTES = {
    'nature': ['#4A7BB0', '#B83A4B', '#3B8256', '#D49A3D', '#7E57C2', '#26A69A', '#EC407A', '#FFA726'],
    'classic': ['#4393C3', '#D6604D', '#31A354', '#756BB1', '#636363', '#E6550D', '#3182BD', '#74C476'],
    'vibrant': ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#F0E442', '#56B4E9', '#E69F00', '#000000']
}

DEFAULT_MARKERS = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']

def get_sig_text(p):
    if np.isnan(p): return "ns"
    if p < 0.001: return "***"
    if p < 0.01: return "**"
    if p < 0.05: return "*"
    if p < 0.1: return "."
    return "ns"

def draw_raincloud_panel(ax, df_pct, cell_type, group_order, group_colors, group_markers, contrasts_to_draw=None):
    """
    Renders a single raincloud subplot with hollow scatter, boxplot, KDE half-violin, and brackets.
    """
    data_by_group = {}
    for g in group_order:
        vals = df_pct[df_pct['Group'] == g][cell_type].values
        data_by_group[g] = vals
    
    all_vals = np.concatenate(list(data_by_group.values()))
    min_v = np.min(all_vals)
    max_v = np.max(all_vals)
    span = max_v - min_v if max_v > min_v else 1.0
    
    # Background subtle horizontal gridlines
    ax.yaxis.grid(True, linestyle='--', alpha=0.6, color='#C0C0C0', zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    
    # Draw each experimental group
    for idx, g in enumerate(group_order):
        vals = data_by_group[g]
        color = group_colors[g]
        marker = group_markers[g]
        x_center = idx
        
        # 1. Left Jittered Hollow Scatter Points
        np.random.seed(42 + idx)
        jitter = np.random.uniform(-0.25, -0.12, size=len(vals))
        ax.scatter(
            x_center + jitter, vals,
            s=46, marker=marker,
            facecolors='none', edgecolors=color,
            linewidth=1.7, alpha=0.9, zorder=4
        )
        
        # 2. Middle Narrow White-Filled Boxplot
        bp = ax.boxplot(
            vals, positions=[x_center], widths=0.10,
            patch_artist=True, showfliers=False, zorder=3,
            boxprops=dict(facecolor='white', edgecolor=color, linewidth=1.5),
            whiskerprops=dict(color=color, linewidth=1.4),
            capprops=dict(color=color, linewidth=1.4),
            medianprops=dict(color=color, linewidth=1.8)
        )
        
        # 3. Right Smooth KDE Half-Violin
        if len(vals) >= 2 and np.std(vals) > 1e-6:
            try:
                kde = gaussian_kde(vals, bw_method='silverman')
                # Slightly extend range for smooth curve
                y_eval = np.linspace(min_v - 0.05 * span, max_v + 0.05 * span, 120)
                density = kde(y_eval)
                density_scaled = (density / np.max(density)) * 0.22
                ax.fill_betweenx(
                    y_eval, x_center + 0.08, x_center + 0.08 + density_scaled,
                    color=color, alpha=0.28, edgecolor=color, linewidth=1.0, zorder=2
                )
            except Exception:
                pass
    
    # 4. Multi-tiered Significance Brackets
    if contrasts_to_draw is None:
        # Default: compare against the first group (or adjacent)
        contrasts_to_draw = []
        if len(group_order) >= 2:
            contrasts_to_draw.append((group_order[0], group_order[1]))
        if len(group_order) >= 3:
            contrasts_to_draw.append((group_order[1], group_order[2]))
        if len(group_order) >= 4:
            contrasts_to_draw.append((group_order[1], group_order[3]))
            
    bracket_y = max_v + 0.12 * span
    step_y = 0.14 * span
    
    drawn_brackets = 0
    for g1, g2 in contrasts_to_draw:
        if g1 in data_by_group and g2 in data_by_group:
            v1 = data_by_group[g1]
            v2 = data_by_group[g2]
            
            # Use Welch's t-test
            try:
                t_stat, p_val = ttest_ind(v1, v2, equal_var=False)
            except Exception:
                p_val = 1.0
                
            sig_sym = get_sig_text(p_val)
            
            idx1 = group_order.index(g1)
            idx2 = group_order.index(g2)
            x_min_b = min(idx1, idx2)
            x_max_b = max(idx1, idx2)
            
            curr_y = bracket_y + drawn_brackets * step_y
            tick_h = 0.03 * span
            
            # Bracket line
            ax.plot(
                [x_min_b, x_min_b, x_max_b, x_max_b],
                [curr_y - tick_h, curr_y, curr_y, curr_y - tick_h],
                color='black', linewidth=1.1, zorder=5
            )
            # Text annotation
            ax.text(
                (x_min_b + x_max_b) / 2.0, curr_y + 0.02 * span,
                sig_sym, ha='center', va='bottom',
                color='black', fontsize=11, fontweight='bold', zorder=5
            )
            drawn_brackets += 1
            
    # Set Limits and Tick Labels
    ax.set_xticks(range(len(group_order)))
    ax.set_xticklabels(group_order, fontweight='bold', fontsize=11)
    ax.set_xlim(-0.6, len(group_order) - 0.4)
    
    top_limit = bracket_y + drawn_brackets * step_y + 0.08 * span
    bottom_limit = max(0, min_v - 0.12 * span)
    ax.set_ylim(bottom_limit, top_limit)
    
    ax.set_title(cell_type.replace('_', ' '), fontsize=13, fontweight='bold', pad=10)
    ax.set_ylabel("Values (%)", fontsize=11, fontweight='bold')
    ax.set_xlabel("Groups", fontsize=11, fontweight='bold')

def plot_dynamic_raincloud(
    input_file,
    output_dir,
    prefix="Fine",
    group_order=None,
    ncols=None,
    panel_w=3.8,
    panel_h=3.2,
    header_h=2.0,
    palette_name="nature",
    custom_colors=None
):
    """
    Main entry point for multi-cell raincloud generation with auto-layout.
    """
    df = pd.read_csv(input_file, sep='\t')
    
    # Identify sample and group columns
    sample_col = 'sample' if 'sample' in df.columns else df.columns[0]
    group_col = 'group' if 'group' in df.columns else df.columns[1]
    
    df = df.rename(columns={sample_col: 'Sample', group_col: 'Group'})
    
    if group_order is None:
        group_order = list(df['Group'].unique())
    else:
        if isinstance(group_order, str):
            group_order = [g.strip() for g in group_order.split(',')]
            
    # Prepare colors
    if custom_colors:
        colors_list = custom_colors.split(',') if isinstance(custom_colors, str) else custom_colors
    else:
        colors_list = DEFAULT_PALETTES.get(palette_name, DEFAULT_PALETTES['nature'])
        
    group_colors = {g: colors_list[i % len(colors_list)] for i, g in enumerate(group_order)}
    group_markers = {g: DEFAULT_MARKERS[i % len(DEFAULT_MARKERS)] for i, g in enumerate(group_order)}
    
    cell_types = [c for c in df.columns if c not in ['Sample', 'Group']]
    n_cells = len(cell_types)
    
    if n_cells == 0:
        print("Error: No cell type columns found in input table.")
        return
        
    # Auto-calculate grid layout
    if ncols is None or ncols <= 0:
        if n_cells <= 3:
            ncols = n_cells
        elif n_cells <= 8:
            ncols = 3 if n_cells in [3, 6] else 4
        elif n_cells <= 12:
            ncols = 4
        else:
            ncols = 4
            
    nrows = math.ceil(n_cells / ncols)
    
    fig_w = panel_w * ncols + 1.2
    fig_h = header_h + panel_h * nrows + 0.8
    
    print(f"Creating multi-panel raincloud plot: {n_cells} cell types | Layout: {nrows} rows x {ncols} cols | Dimensions: {fig_w:.1f} x {fig_h:.1f} inches")
    
    os.makedirs(output_dir, exist_ok=True)
    indiv_dir = os.path.join(output_dir, "individual_cell_types")
    os.makedirs(indiv_dir, exist_ok=True)
    
    # Define contrasts
    contrasts = []
    if len(group_order) >= 2:
        contrasts.append((group_order[0], group_order[1]))
    if len(group_order) >= 3:
        contrasts.append((group_order[1], group_order[2]))
    if len(group_order) >= 4:
        contrasts.append((group_order[1], group_order[3]))
        
    # Multi-panel Overview Figure
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = GridSpec(
        nrows + 1, ncols, figure=fig,
        height_ratios=[header_h / panel_h] + [1.0] * nrows,
        hspace=0.45, wspace=0.35,
        left=0.07, right=0.96, top=0.96, bottom=0.07
    )
    
    # --------------------------------------------------------------------------
    # ISOLATED ROW 0: Zero-Overlap Legend & Significance Header
    # --------------------------------------------------------------------------
    ax_head = fig.add_subplot(gs[0, :])
    ax_head.axis('off')
    
    legend_elements = [
        Line2D([0], [0], marker=group_markers[g], color=group_colors[g],
               label=g, markerfacecolor='none', markeredgewidth=1.8,
               markersize=10, linestyle='None')
        for g in group_order
    ]
    
    # Top Level: Group Legend Box
    leg = ax_head.legend(
        handles=legend_elements,
        title="Experimental Groups",
        title_fontsize=12,
        fontsize=11,
        ncol=len(group_order),
        loc='center',
        bbox_to_anchor=(0.5, 0.82),
        frameon=True,
        edgecolor='#C0C0C0',
        facecolor='#FCFCFC',
        handletextpad=0.6,
        columnspacing=1.8,
        borderpad=0.7
    )
    leg.get_title().set_fontweight('bold')
    
    # Bottom Level: Significance Banner Box
    sig_banner_text = (
        r"$\bf{Significance:}$   "
        r"$\bf{***}$  p < 0.001   |   "
        r"$\bf{**}$  p < 0.01   |   "
        r"$\bf{*}$  p < 0.05   |   "
        r"$\bf{.}$  p < 0.1   |   "
        r"$\bf{ns}$  p $\geq$ 0.1"
    )
    ax_head.text(
        0.5, 0.22, sig_banner_text,
        transform=ax_head.transAxes,
        ha='center', va='center',
        fontsize=11,
        bbox=dict(
            boxstyle='round,pad=0.6',
            facecolor='#F8F9FA',
            edgecolor='#D0D0D0',
            linewidth=1.0
        )
    )
    
    # --------------------------------------------------------------------------
    # SUBPLOTS: Render Each Cell Type
    # --------------------------------------------------------------------------
    for idx, ct in enumerate(cell_types):
        r = (idx // ncols) + 1
        c = idx % ncols
        ax = fig.add_subplot(gs[r, c])
        draw_raincloud_panel(ax, df, ct, group_order, group_colors, group_markers, contrasts)
        
    # Hide unused subplots in last row if any
    total_slots = nrows * ncols
    for idx in range(n_cells, total_slots):
        r = (idx // ncols) + 1
        c = idx % ncols
        ax_blank = fig.add_subplot(gs[r, c])
        ax_blank.axis('off')
        
    # Save Master Figure
    pdf_path = os.path.join(output_dir, f"Cell_Proportion_Significance_Raincloud_{prefix}.pdf")
    png_path = os.path.join(output_dir, f"Cell_Proportion_Significance_Raincloud_{prefix}.png")
    
    fig.savefig(pdf_path, dpi=300)
    fig.savefig(png_path, dpi=300)
    plt.close(fig)
    print(f"Master plot saved:\n  - {pdf_path}\n  - {png_path}")
    
    # --------------------------------------------------------------------------
    # INDIVIDUAL CELL TYPE FIGURES
    # --------------------------------------------------------------------------
    print("Generating individual cell type publication figures...")
    for ct in cell_types:
        fig_single, ax_s = plt.subplots(figsize=(5.2, 4.8))
        draw_raincloud_panel(ax_s, df, ct, group_order, group_colors, group_markers, contrasts)
        
        # Single figure legend
        leg_s = ax_s.legend(
            handles=legend_elements,
            loc='upper right',
            fontsize=9.5,
            frameon=True,
            edgecolor='#C0C0C0',
            facecolor='#FFFFFF'
        )
        
        safe_name = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in ct)
        pdf_s = os.path.join(indiv_dir, f"{prefix}_{safe_name}_raincloud.pdf")
        png_s = os.path.join(indiv_dir, f"{prefix}_{safe_name}_raincloud.png")
        fig_single.tight_layout()
        fig_single.savefig(pdf_s, dpi=300)
        fig_single.savefig(png_s, dpi=300)
        plt.close(fig_single)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Publication-ready Raincloud significance plotting engine.")
    parser.add_argument("-i", "--input", required=True, help="Path to sample percentage TSV file (wide format)")
    parser.add_argument("-o", "--output", default="./plots", help="Output directory for plots")
    parser.add_argument("-p", "--prefix", default="Fine", help="File naming prefix (e.g. Fine, Major)")
    parser.add_argument("-g", "--groups", default=None, help="Comma-separated group order")
    parser.add_argument("--ncols", type=int, default=None, help="Number of columns in multi-panel layout")
    parser.add_argument("--palette", default="nature", choices=["nature", "classic", "vibrant"], help="Color palette")
    parser.add_argument("--colors", default=None, help="Custom comma-separated hex colors")
    parser.add_argument("--panel_w", type=float, default=3.8, help="Subplot width in inches")
    parser.add_argument("--panel_h", type=float, default=3.2, help="Subplot height in inches")
    parser.add_argument("--header_h", type=float, default=2.0, help="Isolated header row height in inches")
    
    args = parser.parse_args()
    
    plot_dynamic_raincloud(
        input_file=args.input,
        output_dir=args.output,
        prefix=args.prefix,
        group_order=args.groups,
        ncols=args.ncols,
        panel_w=args.panel_w,
        panel_h=args.panel_h,
        header_h=args.header_h,
        palette_name=args.palette,
        custom_colors=args.colors
    )
