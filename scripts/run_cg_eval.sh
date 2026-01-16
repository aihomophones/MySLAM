#!/bin/bash

# Activate Python environment
source /media/tam/DATA/3D/Photo-SLAM/venv/bin/activate

# Run TUM RGB-D benchmark
cd /media/tam/DATA/3D/CG-photo/scripts
./tum_rgbd_cg.sh

# Run full evaluation with onekey.py
cd /media/tam/DATA/3D/CG-photo
python3 Photo-SLAM-eval/onekey.py \
    -d /media/tam/DATA/data \
    -r results_cg0/

# Generate comparison report
echo ""
echo "=== Generating Comparison Report ==="
python3 scripts/compare_results.py \
    -b results \
    -m results_cg \
    -o comparison_report.md

echo ""
echo "Done! Check comparison_report.md for results."
