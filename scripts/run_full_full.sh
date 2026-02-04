#!/bin/bash
# Full pipeline: Train + Evaluate Photo-SLAM on Replica (Multiple scenes, multiple runs)
# 
# Usage:
#   ./run_full_pipeline.sh <pa_name> <num_runs> <scene1> [scene2] [scene3] ...
#   ./run_full_pipeline.sh <pa_name> <num_runs> full
#
# Examples:
#   ./run_full_pipeline.sh pa9 3 office0                    # office0 x 3 runs
#   ./run_full_pipeline.sh pa12 1 full                      # Run all 8 scenes x 1 run

# Don't use set -e, we handle errors manually

# Parse arguments
PA_NAME="${1:?Usage: ./run_full_pipeline.sh <pa_name> <num_runs> <scene1> [scene2] ...}"
NUM_RUNS="${2:?Missing number of runs}"
shift 2
SCENES=("$@")

# === Check for "full" keyword ===
if [ "${SCENES[0]}" == "full" ]; then
    echo ">> Mode 'full' detected: Automatically selecting all 8 Replica scenes."
    SCENES=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")
fi

if [ ${#SCENES[@]} -eq 0 ]; then
    echo "Error: No scenes specified!"
    echo "Usage: ./run_full_pipeline.sh <pa_name> <num_runs> <scene1> [scene2] ..."
    echo "       ./run_full_pipeline.sh <pa_name> <num_runs> full"
    exit 1
fi

# Paths
BASE_DIR="/home/crl/lehieu/CG-photo"
GT_DATA_BASE="/home/crl/lehieu/MyPhotoSLAM/data/Replica"
GT_MESH_BASE="/home/crl/lehieu/MyPhotoSLAM/data/Replica/cull_replica_mesh"
# VENV_PATH="/media/tam/DATA/3D/Photo-SLAM/venv" # Unused in original script logic but kept if needed
# TSDF_ENV_PATH="${BASE_DIR}/scripts/tsdf_env"   # Unused
CONFIG_FILE="${CONFIG_FILE:-${BASE_DIR}/cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml}"

cd "$BASE_DIR"

# Activate conda environment (User requested slam_env)
source ~/miniconda3/etc/profile.d/conda.sh
if conda activate slam_env 2>/dev/null; then
    echo ">> Activated conda environment: slam_env"
elif conda activate photoslam 2>/dev/null; then
    echo ">> Activated conda environment: photoslam"
elif conda activate slam_env 2>/dev/null; then
    echo ">> Activated conda environment: slam_env"
else
    echo ">> Warning: Could not activate 'slam_env', 'photo-slam', or 'photoslam'. Staying in current environment."
fi

# Capture the correct python executable
if [ -n "$CONDA_PREFIX" ]; then
    PYTHON_EXE="$CONDA_PREFIX/bin/python"
    echo ">> Using Python from Conda: $PYTHON_EXE"
else
    PYTHON_EXE=$(which python)
    echo ">> Using System Python: $PYTHON_EXE"
fi

# Extract loss weights from config
LAMBDA_GEO=$(grep "Optimization.lambda_geo:" "$CONFIG_FILE" | awk '{print $2}')
LAMBDA_SMOOTH=$(grep "Optimization.lambda_smooth:" "$CONFIG_FILE" | awk '{print $2}')
LAMBDA_VAR=$(grep "Optimization.lambda_var:" "$CONFIG_FILE" | awk '{print $2}')
LAMBDA_ISO=$(grep "Optimization.lambda_iso:" "$CONFIG_FILE" | awk '{print $2}')
LAMBDA_ALIGN=$(grep "Optimization.lambda_align:" "$CONFIG_FILE" | awk '{print $2}')

echo "=============================================="
echo "  Full Pipeline: ${PA_NAME}"
echo "  Scenes: ${SCENES[*]}"
echo "  Runs per scene: ${NUM_RUNS}"
echo "=============================================="
echo ""
echo "=== LOSS WEIGHTS (from config) ==="
echo "lambda_geo:    ${LAMBDA_GEO}"
echo "lambda_smooth: ${LAMBDA_SMOOTH}"
echo "lambda_var:    ${LAMBDA_VAR}"
echo "lambda_iso:    ${LAMBDA_ISO}"
echo "lambda_align:  ${LAMBDA_ALIGN}"
echo ""

# Create results summary file (append mode - only add header if file doesn't exist)
SUMMARY_ALL="${BASE_DIR}/results_${PA_NAME}/all_results.csv"
FAILED_LOG="${BASE_DIR}/results_${PA_NAME}/failed_runs.txt"
mkdir -p "${BASE_DIR}/results_${PA_NAME}"

# Only write header if CSV doesn't exist or is empty
if [ ! -f "$SUMMARY_ALL" ] || [ ! -s "$SUMMARY_ALL" ]; then
    echo "scene,run,psnr,ssim,lpips,ate_rmse,accuracy,completion,comp_ratio,chamfer" > "$SUMMARY_ALL"
fi
echo "# Failed runs log - $(date)" >> "$FAILED_LOG"

# Function to run single scene
run_single_scene() {
    local SCENE=$1
    local RUN=$2
    local RESULT_DIR="${BASE_DIR}/results_${PA_NAME}/${SCENE}_run${RUN}"
    local GT_DATA_DIR="${GT_DATA_BASE}/${SCENE}"
    local GT_MESH="${GT_MESH_BASE}/${SCENE}.ply"
    
    echo ""
    echo "======================================================"
    echo "  Running: ${SCENE} (Run ${RUN}/${NUM_RUNS})"
    echo "======================================================"
    
    # Check if run already finished successfully
    if [ -f "${RESULT_DIR}/summary.txt" ]; then
        # Check if the result is valid (PSNR should not be empty)
        if grep -q "PSNR: $" "${RESULT_DIR}/summary.txt"; then
            echo "[!] Found invalid summary (empty metrics). Re-running..."
            rm -rf "$RESULT_DIR"
        else
            echo "[v] Run already completed successfully (summary.txt exists). Skipping..."
            return 0
        fi
    fi

    # Delete existing results (only if incomplete)
    if [ -d "$RESULT_DIR" ]; then
        echo "[!] Deleting incomplete result: $RESULT_DIR"
        rm -rf "$RESULT_DIR"
    fi

    # Create directory explicitly for log file
    mkdir -p "$RESULT_DIR"
    
    # Step 1: Training
    echo "--- Training ---"
    cd "$BASE_DIR"
    if ! ./bin/replica_rgbd \
        ORB-SLAM3/Vocabulary/ORBvoc.txt \
        cfg/ORB_SLAM3/RGB-D/Replica/${SCENE}.yaml \
        "$CONFIG_FILE" \
        "${GT_DATA_DIR}" \
        "results_${PA_NAME}/${SCENE}_run${RUN}" \
        no_viewer > "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] TRAINING FAILED: ${SCENE} run ${RUN} (Exit Code: $?)"
        tail -n 20 "${RESULT_DIR}/run.log"
        echo "${SCENE},${RUN},FAILED,training" >> "$FAILED_LOG"
        echo "${SCENE},${RUN},FAILED,FAILED,FAILED,FAILED,FAILED,FAILED" >> "$SUMMARY_ALL"
        return 1
    fi

    # Check if trajectory was saved (indicates successful completion)
    if [ ! -f "${RESULT_DIR}/CameraTrajectory_TUM.txt" ]; then
        echo "[X] TRAINING INCOMPLETE: CameraTrajectory_TUM.txt missing!"
        tail -n 20 "${RESULT_DIR}/run.log"
        echo "${SCENE},${RUN},FAILED,training_incomplete" >> "$FAILED_LOG"
        echo "${SCENE},${RUN},FAILED,FAILED,FAILED,FAILED,FAILED,FAILED" >> "$SUMMARY_ALL"
        return 1
    fi
    
    # Step 2: Photometric Evaluation
    echo "--- Photometric Evaluation ---"
    cd "/home/crl/lehieu/Photo-SLAM-eval"
    if ! "$PYTHON_EXE" run.py "/home/crl/lehieu/CG-photo/results_${PA_NAME}/${SCENE}_run${RUN}" "${GT_DATA_DIR}" >> "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] PHOTOMETRIC EVAL FAILED"
        echo "${SCENE},${RUN},FAILED,photometric_eval" >> "$FAILED_LOG"
        return 1
    fi
    
    # Calculate metrics
    PSNR=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/psnr.txt")
    SSIM=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/ssim.txt")
    LPIPS=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/lpips.txt")
    
    # Extract ATE (RMSE) from metrics_traj.txt (first occurrence is Translation RMSE)
    if [ -f "${RESULT_DIR}/metrics_traj.txt" ]; then
        ATE_RMSE=$(grep "rmse" "${RESULT_DIR}/metrics_traj.txt" | head -n 1 | awk '{printf "%.4f", $2}')
    else
        ATE_RMSE="N/A"
    fi

    # Step 3: Generate Mesh (using cameras.json for correct coordinate alignment)
    echo "--- Generating Mesh ---"
    cd "$BASE_DIR"
    
    # Find shutdown directory containing cameras.json
    SHUTDOWN_DIR=$(ls -d ${RESULT_DIR}/*_shutdown 2>/dev/null | head -1)
    JSON_PATH="${SHUTDOWN_DIR}/ply/cameras.json"
    DEPTH_DIR="${SHUTDOWN_DIR}/depth"
    GT_TRAJ="${GT_DATA_DIR}/traj.txt"
    
    mkdir -p "${RESULT_DIR}/meshes"
    
    if [ ! -f "$JSON_PATH" ]; then
        echo "[X] ERROR: cameras.json not found: $JSON_PATH"
        echo "${SCENE},${RUN},ERROR,cameras.json not found" >> "$FAILED_LOG"
        return 1
    fi
    
    # Generate mesh using cameras.json with GT trajectory for coordinate alignment
    if ! "$PYTHON_EXE" scripts/generate_mesh_from_json.py \
        --json_path "$JSON_PATH" \
        --depth_dir "$DEPTH_DIR" \
        --output "${RESULT_DIR}/meshes/${SCENE}_json_aligned.ply" \
        --voxel_size 0.01 \
        --depth_scale 6553.5 \
        --max_depth 10.0 \
        --gt_traj "$GT_TRAJ" >> "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] MESH GENERATION FAILED"
        echo "${SCENE},${RUN},FAILED,mesh_generation" >> "$FAILED_LOG"
        return 1
    fi
    MESH_FILE="${RESULT_DIR}/meshes/${SCENE}_json_aligned.ply"
    
    # Step 4: Geometric Evaluation
    echo "--- Geometric Evaluation ---"
    cd "${BASE_DIR}/neural_slam_eval-main"
    if ! EVAL_OUTPUT=$("$PYTHON_EXE" eval_recon.py \
        --rec_mesh "$MESH_FILE" \
        --gt_mesh "${GT_MESH}" \
        -3d 2>&1); then
        echo "[X] GEOMETRIC EVAL FAILED"
        echo "$EVAL_OUTPUT" >> "${RESULT_DIR}/run.log"
        echo "${SCENE},${RUN},FAILED,geometric_eval" >> "$FAILED_LOG"
        return 1
    fi
    
    ACC=$(echo "$EVAL_OUTPUT" | grep "accuracy:" | awk '{printf "%.4f", $2}')
    COMP=$(echo "$EVAL_OUTPUT" | grep "completion:" | awk '{printf "%.4f", $2}')
    COMP_RATIO=$(echo "$EVAL_OUTPUT" | grep "completion ratio:" | awk '{printf "%.2f", $3}')
    CHAMFER=$(echo "$EVAL_OUTPUT" | grep "chamfer:" | awk '{printf "%.4f", $2}')
    
    # Print summary for this run
    echo ""
    echo "--- ${SCENE} Run ${RUN} Results ---"
    echo "PSNR: ${PSNR} | SSIM: ${SSIM} | LPIPS: ${LPIPS} | ATE: ${ATE_RMSE}"
    echo "Acc: ${ACC}cm | Comp: ${COMP}cm | Chamfer: ${CHAMFER}cm | Ratio: ${COMP_RATIO}%"
    
    # Append to CSV
    echo "${SCENE},${RUN},${PSNR},${SSIM},${LPIPS},${ATE_RMSE},${ACC},${COMP},${COMP_RATIO},${CHAMFER}" >> "$SUMMARY_ALL"
    
    # Save individual summary
    cat > "${RESULT_DIR}/summary.txt" << EOF
PA: ${PA_NAME}, Scene: ${SCENE}, Run: ${RUN}

# Loss Weights
lambda_geo: ${LAMBDA_GEO}
lambda_smooth: ${LAMBDA_SMOOTH}
lambda_var: ${LAMBDA_VAR}
lambda_iso: ${LAMBDA_ISO}
lambda_align: ${LAMBDA_ALIGN}

# Metrics
PSNR: ${PSNR}
SSIM: ${SSIM}
LPIPS: ${LPIPS}
ATE_RMSE: ${ATE_RMSE}
Accuracy: ${ACC}
Completion: ${COMP}
Completion_Ratio: ${COMP_RATIO}
Chamfer: ${CHAMFER}
EOF
}

# Main loop
TOTAL_RUNS=$((${#SCENES[@]} * NUM_RUNS))
CURRENT=0

for SCENE in "${SCENES[@]}"; do
    for ((RUN=1; RUN<=NUM_RUNS; RUN++)); do
        CURRENT=$((CURRENT + 1))
        echo ""
        echo "######################################################"
        echo "  Progress: ${CURRENT}/${TOTAL_RUNS}"
        echo "######################################################"
        run_single_scene "$SCENE" "$RUN"
    done
done

# Final Summary
cd "$BASE_DIR"
echo ""
echo "=============================================="
echo "  ALL RESULTS: ${PA_NAME}"
echo "=============================================="
echo ""
cat "$SUMMARY_ALL" | column -t -s','
echo ""
echo "[✓] All results saved to: ${SUMMARY_ALL}"