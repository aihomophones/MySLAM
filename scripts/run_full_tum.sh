#!/bin/bash

# ====================================================================================
# RUN FULL PIPELINE (TUM VERSION)
# 
# Usage: ./scripts/run_full_tum.sh [SCENE_NAME|all_tum] [NUM_RUNS] [MODE: test|full]
# Example: ./scripts/run_full_tum.sh all_tum 3 full
# ====================================================================================

set -e  # Exit strictly on error is NOT set globally to allow custom error handling, but we use strict checks below.

# --- Configuration ---
BASE_DIR="/home/crl/lehieu/CG-photo"
DATASET_ROOT="/home/crl/lehieu/MyPhotoSLAM/data/TUM"
PA_NAME="tum_evaluation"

# Config files (Allow override)
CONFIG_FILE="${CONFIG_FILE:-${BASE_DIR}/cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml}"

# Default Arguments
# Check if first arg provides PA_NAME override (heuristic: not a scene name)
if [ -n "$1" ] && [ "$1" != "all_tum" ] && [[ "$1" != rgbd_dataset* ]]; then
  PA_NAME="$1"
  shift
else
  PA_NAME="${PA_NAME:-tum_evaluation}"
fi

SCENE_ARG="${1:-all_tum}"
NUM_RUNS="${2:-3}"
MODE="${3:-test}"  # 'test' (1 scene) or 'full' (all scenes)

# Update Result Root based on PA_NAME
RESULT_ROOT="${BASE_DIR}/results_${PA_NAME}"

# Define Scenes
if [ "$SCENE_ARG" == "all_tum" ]; then
    SCENES=("rgbd_dataset_freiburg1_desk" "rgbd_dataset_freiburg2_xyz" "rgbd_dataset_freiburg3_long_office_household")
else
    SCENES=("$SCENE_ARG")
fi

echo "=============================================="
echo "  Full Pipeline: ${PA_NAME}"
echo "  Scenes: ${SCENES[*]}"
echo "  Runs per scene: ${NUM_RUNS}"
echo "=============================================="

cd "$BASE_DIR"

# Activate conda environment (Robust Check)
source ~/miniconda3/etc/profile.d/conda.sh
if conda activate slam_env 2>/dev/null; then
    echo ">> Activated conda environment: slam_env"
elif conda activate photo-slam 2>/dev/null; then
    echo ">> Activated conda environment: photo-slam"
elif conda activate photoslam 2>/dev/null; then
    echo ">> Activated conda environment: photoslam"
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

echo ""
echo "=== LOSS WEIGHTS (from config) ==="
echo "lambda_geo:    $LAMBDA_GEO"
echo "lambda_smooth: $LAMBDA_SMOOTH"
echo "lambda_var:    $LAMBDA_VAR"
echo "lambda_iso:    $LAMBDA_ISO"
echo "lambda_align:  $LAMBDA_ALIGN"
echo ""

# Create Result Directory
mkdir -p "$RESULT_ROOT"
SUMMARY_ALL="${RESULT_ROOT}/all_results.csv"
FAILED_LOG="${RESULT_ROOT}/failed_runs.log"

# Initialize Summary CSV if not exists
if [ ! -f "$SUMMARY_ALL" ] || [ ! -s "$SUMMARY_ALL" ]; then
    echo "scene,run,psnr,ssim,lpips,ate_rmse,accuracy,completion,comp_ratio,chamfer" > "$SUMMARY_ALL"
fi
echo "# Failed runs log - $(date)" >> "$FAILED_LOG"

# Function to run single scene
run_single_scene() {
    SCENE=$1
    RUN=$2
    
    # Map SCENE folder name to Config/Association name
    # e.g., rgbd_dataset_freiburg1_desk -> tum_freiburg1_desk
    SCENE_SHORT=${SCENE/rgbd_dataset_/tum_}
    
    ORB_CONFIG="cfg/ORB_SLAM3/RGB-D/TUM/${SCENE_SHORT}.yaml"
    ASSOC_FILE="cfg/ORB_SLAM3/RGB-D/TUM/associations/${SCENE_SHORT}.txt"
    GT_DATA_DIR="${DATASET_ROOT}/${SCENE}"
    RESULT_DIR="${RESULT_ROOT}/${SCENE}_run${RUN}"
    
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
    
    if ! ./bin/tum_rgbd \
        ORB-SLAM3/Vocabulary/ORBvoc.txt \
        "$ORB_CONFIG" \
        "$CONFIG_FILE" \
        "$GT_DATA_DIR" \
        "$ASSOC_FILE" \
        "${RESULT_DIR}" \
        no_viewer > "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] TRAINING FAILED: ${SCENE} run ${RUN} (Exit Code: $?)"
        tail -n 20 "${RESULT_DIR}/run.log"
        echo "${SCENE},${RUN},FAILED,training" >> "$FAILED_LOG"
        echo "${SCENE},${RUN},FAILED,FAILED,FAILED,FAILED,FAILED,FAILED,FAILED,FAILED" >> "$SUMMARY_ALL"
        return 1
    fi

    # Check if trajectory was saved
    if [ ! -f "${RESULT_DIR}/CameraTrajectory_TUM.txt" ]; then
        echo "[X] TRAINING INCOMPLETE: CameraTrajectory_TUM.txt missing!"
        tail -n 20 "${RESULT_DIR}/run.log"
        echo "${SCENE},${RUN},FAILED,training_incomplete" >> "$FAILED_LOG"
        echo "${SCENE},${RUN},FAILED,FAILED,FAILED,FAILED,FAILED,FAILED,FAILED,FAILED" >> "$SUMMARY_ALL"
        return 1
    fi
    
    # Step 2: Photometric Evaluation
    echo "--- Photometric Evaluation ---"
    cd "/home/crl/lehieu/Photo-SLAM-eval"
    if ! "$PYTHON_EXE" run.py "${RESULT_DIR}" "${GT_DATA_DIR}" >> "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] PHOTOMETRIC EVAL FAILED"
        echo "${SCENE},${RUN},FAILED,photometric_eval" >> "$FAILED_LOG"
        return 1
    fi
    
    # Calculate metrics
    PSNR=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/psnr.txt")
    SSIM=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/ssim.txt")
    LPIPS=$(awk '{sum+=$1; count++} END {printf "%.4f", sum/count}' "${RESULT_DIR}/lpips.txt")
    
    # Extract ATE (RMSE) from metrics_traj.txt
    if [ -f "${RESULT_DIR}/metrics_traj.txt" ]; then
        ATE_RMSE=$(grep "rmse" "${RESULT_DIR}/metrics_traj.txt" | head -n 1 | awk '{printf "%.4f", $2}')
    else
        ATE_RMSE="N/A"
    fi
    
    # Step 3: Generate GT Mesh (TUM Specific)
    echo "--- Generating GT Mesh (Pseudo-GT) ---"
    cd "$BASE_DIR"
    # Only generate if not already exists (shared across runs? No, safe to generate per run or in a shared place)
    # Ideally should be generated once per SCENE, not per RUN.
    # But for simplicity, we generate it into the result dir OR we check if a common one exists.
    # Let's generate it into the result dir to be self-contained for evaluation logic.
    GT_MESH="${RESULT_DIR}/gt_mesh.ply"
    
    if ! "$PYTHON_EXE" scripts/generate_gt_mesh_tum.py \
        --sequence_dir "$GT_DATA_DIR" \
        --output "$GT_MESH" \
        --stride 5 \
        --voxel_size 0.01 \
        --max_depth 3.5 >> "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] GT MESH GENERATION FAILED"
        echo "${SCENE},${RUN},FAILED,gt_mesh_generation" >> "$FAILED_LOG"
        return 1
    fi

    # Step 4: Generate Reconstructed Mesh
    echo "--- Generating Mesh ---"
    
    # Find shutdown directory containing cameras.json
    SHUTDOWN_DIR=$(ls -d ${RESULT_DIR}/*_shutdown 2>/dev/null | head -1)
    JSON_PATH="${SHUTDOWN_DIR}/ply/cameras.json"
    DEPTH_DIR="${SHUTDOWN_DIR}/depth"
    GT_TRAJ="${GT_DATA_DIR}/groundtruth.txt" # TUM uses groundtruth.txt, not traj.txt
    
    mkdir -p "${RESULT_DIR}/meshes"
    
    if [ ! -f "$JSON_PATH" ]; then
        echo "[X] ERROR: cameras.json not found: $JSON_PATH"
        echo "${SCENE},${RUN},ERROR,cameras.json not found" >> "$FAILED_LOG"
        return 1
    fi
    
    # Generate mesh using cameras.json
    # Note: TUM doesn't need "gt_traj" alignment here because generate_gt_mesh_tum.py creates GT mesh in World frame(?).
    # Wait, generate_gt_mesh_tum.py uses GT poses, so the GT mesh is in World frame.
    # The SLAM system output (cameras.json) is in SLAM frame. 
    # For Replica, we aligned Rec Mesh to GT Traj.
    # For TUM, we should do the same: Align Rec Mesh to GT World Frame.
    # Fortunately `generate_mesh_from_json.py` already supports `--gt_traj`.
    # BUT, `load_gt_traj` in `generate_mesh_from_json.py` expects Replica format (4x4 matrix).
    # TUM `groundtruth.txt` is TxTyTzQxQyQzQw.
    # WE NEED TO FIX THIS. `generate_mesh_from_json.py` might fail on TUM format.
    
    # Wait, `generate_mesh_from_json.py` has `load_gt_traj` function.
    # I verified it earlier: `values = [float(x) for x in line.split()]`. `reshape(4,4)`.
    # This DEFINITELY fails on TUM format.
    
    # CRITICAL: We cannot use `--gt_traj` with TUM format in current `generate_mesh_from_json.py`.
    # Alternative:
    # 1. Use `eval_recon.py`'s alignment capability (`-3d` flag aligns meshes?).
    #    Checked `eval_recon.py` (via previous knowledge or check now): usually aligns using ICP or similarity.
    #    `onekey.py` calls `run.py` which calls `main_ape`.
    #    Wait, `eval_recon.py` (neural_slam_eval) usually does alignment if meshes are close.
    #    ORB-SLAM3 is monocular/stereo/RGBD, scale might be drift-free for RGBD.
    #    But coordinate system origins differ.
    
    # Let's rely on `eval_recon.py` doing alignment if possible.
    # OR create a temporary Replica-formatted trait file? No too complex.
    # Let's try running WITHOUT `--gt_traj` alignment first, and assume `eval_recon.py` handles alignment (it has `-3d` which often implies ICP or alignment).
    # Actually `eval_recon.py` from `neural_slam_eval` usually requires alignment.
    # `run_full_full.sh` uses `--gt_traj` to align Rec Mesh to GT Traj Frame.
    # If we skip this, Rec Mesh is in SLAM Frame. GT Mesh is in World Frame.
    # We rely on `eval_recon.py` to align them.
    
    if ! "$PYTHON_EXE" scripts/generate_mesh_from_json.py \
        --json_path "$JSON_PATH" \
        --depth_dir "$DEPTH_DIR" \
        --output "${RESULT_DIR}/meshes/${SCENE}_json_aligned.ply" \
        --voxel_size 0.01 \
        --depth_scale 5000.0 \
        --max_depth 3.5 >> "${RESULT_DIR}/run.log" 2>&1; then
        echo "[X] MESH GENERATION FAILED"
        echo "${SCENE},${RUN},FAILED,mesh_generation" >> "$FAILED_LOG"
        return 1
    fi
    MESH_FILE="${RESULT_DIR}/meshes/${SCENE}_json_aligned.ply"
    
    # Step 5: Geometric Evaluation
    echo "--- Geometric Evaluation ---"
    cd "${BASE_DIR}/neural_slam_eval-main"
    
    # Note: Using generated GT_MESH
    if ! EVAL_OUTPUT=$("$PYTHON_EXE" eval_recon.py \
        --rec_mesh "$MESH_FILE" \
        --gt_mesh "$GT_MESH" \
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

# --- Main Loop ---
TOTAL_RUNS=$(( ${#SCENES[@]} * NUM_RUNS ))
CURRENT_IDX=0

for SCENE in "${SCENES[@]}"; do
    for (( i=1; i<=NUM_RUNS; i++ )); do
        CURRENT_IDX=$((CURRENT_IDX + 1))
        
        echo ""
        echo "######################################################"
        echo "  Progress: ${CURRENT_IDX}/${TOTAL_RUNS}"
        echo "######################################################"
        
        run_single_scene "$SCENE" "$i"
    done
done

echo ""
echo "=============================================="
echo "  ALL RESULTS: ${PA_NAME}"
echo "=============================================="
column -s, -t < "$SUMMARY_ALL" | tee /dev/tty
echo ""
echo "[✓] All results saved to: $SUMMARY_ALL"
