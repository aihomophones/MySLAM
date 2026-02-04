#!/bin/bash

# Usage: ./scripts/update_metrics.sh [RESULT_DIR_NAME]
# Example: ./scripts/update_metrics.sh results_all_0

BASE_DIR="/home/crl/lehieu/CG-photo"
RESULT_NAME="${1:-results_all_0}"
RESULT_ROOT="${BASE_DIR}/${RESULT_NAME}"

if [ ! -d "$RESULT_ROOT" ]; then
    echo "Error: Directory $RESULT_ROOT does not exist."
    exit 1
fi

CSV_FILE="${RESULT_ROOT}/all_results.csv"
echo "scene,run,psnr,ssim,lpips,ate_rmse,accuracy,completion,comp_ratio,chamfer" > "$CSV_FILE"

echo "Updating metrics for $RESULT_NAME..."

# Iterate through all directories in results
# Expected format: scene_runX
for DIR_PATH in "$RESULT_ROOT"/*_run*; do
    if [ -d "$DIR_PATH" ]; then
        DIR_NAME=$(basename "$DIR_PATH") # e.g. room2_run1
        
        # Parse Scene and Run from directory name
        # Assumption: name is like scene_runN. 
        # But wait, scenes can be 'office0', 'office1'.
        # Regex to split?
        # scene is everything before _run
        SCENE=${DIR_NAME%_run*}
        RUN_PART=${DIR_NAME##*_}  # run1
        RUN=${RUN_PART#run}       # 1
        
        # Read Metrics
        PSNR="N/A"
        SSIM="N/A"
        LPIPS="N/A"
        ATE_RMSE="N/A"
        ACC="N/A"
        COMP="N/A"
        COMP_RATIO="N/A"
        CHAMFER="N/A"
        
        # 1. Image Metrics
        if [ -f "${DIR_PATH}/psnr.txt" ]; then
             PSNR=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${DIR_PATH}/psnr.txt")
        fi
        if [ -f "${DIR_PATH}/ssim.txt" ]; then
             SSIM=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${DIR_PATH}/ssim.txt")
        fi
        if [ -f "${DIR_PATH}/lpips.txt" ]; then
             LPIPS=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${DIR_PATH}/lpips.txt")
        fi
        
        # 2. ATE Metric
        if [ -f "${DIR_PATH}/metrics_traj.txt" ]; then
            ATE_RMSE=$(grep "rmse" "${DIR_PATH}/metrics_traj.txt" | head -n 1 | awk '{printf "%.4f", $2}')
        fi
        
        # 3. Geometric Metrics (from log or specific file?)
        # Only available if outputted to run.log or a file.
        # run_full_full.sh outputs to console and parses it. 
        # But `eval_recon.py` usually just prints to stdout.
        # Check if `summary.txt` exists?
        
        if [ -f "${DIR_PATH}/summary.txt" ]; then
             # Try to read from summary.txt if available
             # PSNR: 35.8123
             PSNR_SUM=$(grep "PSNR:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$PSNR_SUM" ] && PSNR=$PSNR_SUM
             
             SSIM_SUM=$(grep "SSIM:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$SSIM_SUM" ] && SSIM=$SSIM_SUM
             
             LPIPS_SUM=$(grep "LPIPS:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$LPIPS_SUM" ] && LPIPS=$LPIPS_SUM
             
             ACC_SUM=$(grep "Accuracy:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$ACC_SUM" ] && ACC=$ACC_SUM
             
             COMP_SUM=$(grep "Completion:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$COMP_SUM" ] && COMP=$COMP_SUM
             
             RAT_SUM=$(grep "Completion_Ratio:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$RAT_SUM" ] && COMP_RATIO=$RAT_SUM
             
             CHAM_SUM=$(grep "Chamfer:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$CHAM_SUM" ] && CHAMFER=$CHAM_SUM
             
             # Also try ATE from summary (though user said it's missing)
             ATE_SUM=$(grep "ATE_RMSE:" "${DIR_PATH}/summary.txt" | awk '{print $2}')
             [ ! -z "$ATE_SUM" ] && ATE_RMSE=$ATE_SUM
        fi
        
        # If ATE is still N/A, we trust the logic above (reading metrics_traj.txt)
        
        echo "${SCENE},${RUN},${PSNR},${SSIM},${LPIPS},${ATE_RMSE},${ACC},${COMP},${COMP_RATIO},${CHAMFER}" >> "$CSV_FILE"
        echo "Processed ${DIR_NAME}: ATE=${ATE_RMSE}"
        
        # Update summary.txt with ATE if missing
        if [ -f "${DIR_PATH}/summary.txt" ] && ! grep -q "ATE_RMSE:" "${DIR_PATH}/summary.txt"; then
             # Insert ATE after LPIPS
             sed -i "/LPIPS:/a ATE_RMSE: ${ATE_RMSE}" "${DIR_PATH}/summary.txt"
        fi
    fi
done

echo "Done. Updated CSV saved to $CSV_FILE"
column -s, -t < "$CSV_FILE"
