#!/usr/bin/env bash
# ==============================================================================
# Script: run_all_proportion_pipeline.sh
# Skill: B05-细胞比例统计图
# Description: One-click bash workflow to run statistical calculations,
#   publication dynamic raincloud plots, and multi-dimensional composite plots.
# ==============================================================================

set -euo pipefail

INPUT=""
ANNO=""
GROUP=""
OUTPUT="./cell_proportion_analysis"
GROUP_ORDER=""
SAMPLE_ORDER=""
CELLTYPE_COLS="cell_type_fine,cell_type_major"
CONTAINER_SIF="/mnt/test/FCX/sif/sc_Analysis_V4.0.sif"

usage() {
  echo "Usage: $0 -i <input_file> [-a <anno_file>] [-g <group_file>] [-o <output_dir>] [--group_order <order>] [--sample_order <order>] [--sif <path>]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    -i|--input) INPUT="$2"; shift 2 ;;
    -a|--anno) ANNO="$2"; shift 2 ;;
    -g|--group) GROUP="$2"; shift 2 ;;
    -o|--output) OUTPUT="$2"; shift 2 ;;
    --group_order) GROUP_ORDER="$2"; shift 2 ;;
    --sample_order) SAMPLE_ORDER="$2"; shift 2 ;;
    --celltype_cols) CELLTYPE_COLS="$2"; shift 2 ;;
    --sif) CONTAINER_SIF="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ -z "$INPUT" ]]; then
  echo "Error: --input is required."
  usage
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================================================"
echo " Starting B05 · 单细胞细胞比例统计与显著性分析 Pipeline"
echo "================================================================================"
echo "Input: $INPUT"
echo "Output: $OUTPUT"

RUN_CMD=""
if [[ -f "$CONTAINER_SIF" ]]; then
  echo "Executing within Apptainer container: $CONTAINER_SIF"
  RUN_CMD="apptainer exec --bind /mnt:/mnt $CONTAINER_SIF"
fi

# Step 1: Run Statistics in R
echo ">>> Step 1/3: Calculating statistics and generating master tables..."
CMD_R="Rscript $SCRIPT_DIR/run_proportion_stats.R -i $INPUT -o $OUTPUT --celltype_cols $CELLTYPE_COLS"
if [[ -n "$ANNO" ]]; then CMD_R="$CMD_R -a $ANNO"; fi
if [[ -n "$GROUP" ]]; then CMD_R="$CMD_R -g $GROUP"; fi
if [[ -n "$GROUP_ORDER" ]]; then CMD_R="$CMD_R --group_order $GROUP_ORDER"; fi
if [[ -n "$SAMPLE_ORDER" ]]; then CMD_R="$CMD_R --sample_order $SAMPLE_ORDER"; fi

if [[ -n "$RUN_CMD" ]]; then
  $RUN_CMD $CMD_R
else
  eval $CMD_R
fi

# Step 2: Render Dynamic Raincloud in Python
echo ">>> Step 2/3: Rendering publication raincloud plots..."
TAB_DIR="$OUTPUT/summary/tables"
PLOT_DIR="$OUTPUT/summary/plots"

IFS=',' read -ra COLS <<< "$CELLTYPE_COLS"
for col in "${COLS[@]}"; do
  prefix="${col#cell_type_}"
  # Capitalize first letter
  prefix_title="$(tr '[:lower:]' '[:upper:]' <<< ${prefix:0:1})${prefix:1}"
  tsv_file="$TAB_DIR/Cell_Proportion_${prefix_title}_Sample_Percentages.tsv"
  
  if [[ -f "$tsv_file" ]]; then
    echo "Rendering raincloud for: $prefix_title..."
    CMD_PY="python3 $SCRIPT_DIR/plot_dynamic_raincloud.py -i $tsv_file -o $PLOT_DIR -p $prefix_title"
    if [[ -n "$GROUP_ORDER" ]]; then CMD_PY="$CMD_PY -g $GROUP_ORDER"; fi
    
    if [[ -n "$RUN_CMD" ]]; then
      $RUN_CMD $CMD_PY
    else
      eval $CMD_PY
    fi
  fi
done

# Step 3: Render Multi-Dimensional Composite Plots in R
echo ">>> Step 3/3: Rendering multi-dimensional composite bubble-bar plots..."
META_RDS="$OUTPUT/metadata_annotated.rds"
if [[ -f "$META_RDS" ]]; then
  for col in "${COLS[@]}"; do
    prefix="${col#cell_type_}"
    prefix_title="$(tr '[:lower:]' '[:upper:]' <<< ${prefix:0:1})${prefix:1}"
    
    CMD_COMP="Rscript $SCRIPT_DIR/plot_multidim_composite.R -i $META_RDS -o $PLOT_DIR -c $col -p $prefix_title"
    if [[ -n "$GROUP_ORDER" ]]; then CMD_COMP="$CMD_COMP -g $GROUP_ORDER"; fi
    if [[ -n "$SAMPLE_ORDER" ]]; then CMD_COMP="$CMD_COMP -s $SAMPLE_ORDER"; fi
    
    if [[ -n "$RUN_CMD" ]]; then
      $RUN_CMD $CMD_COMP
    else
      eval $CMD_COMP
    fi
  done
fi

echo "================================================================================"
echo " Pipeline Finished Successfully!"
echo " Results Delivered to: $OUTPUT/summary"
echo "================================================================================"
