#!/bin/bash
# =============================================================================
# Replica RGB-D PA6 Full Pipeline Script
# =============================================================================
# This script performs:
#   1. Run training on Replica dataset with PA6 (L_geo λ=0.2)
#   2. Evaluate rendering metrics with onekey.py (PSNR, SSIM, LPIPS, ATE)
#   3. Generate TSDF meshes from rendered depth
#   4. Evaluate meshes against Replica ground truth meshes
# =============================================================================

set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# =============================================================================
# Configuration
# =============================================================================
DATASET_PATH="/media/tam/DATA/data"
RESULT_BASE="../results_replica_pa6"
MESH_OUTPUT_DIR="../meshes_replica_pa6"
GT_MESH_DIR="${DATASET_PATH}/Replica"  # Adjust if GT meshes are elsewhere

# Training settings
ITERATIONS=5  # Number of training iterations (runs)
START_ITER=0

# Mesh generation settings
VOXEL_SIZE=0.01
SDF_TRUNC=0.04
DEPTH_SCALE=6553.5  # Replica uses different depth scale
DEPTH_TRUNC=10.0

# Replica scenes
SCENES=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")

# Export OpenCV library path
export LD_LIBRARY_PATH=/media/tam/DATA/3D/Photo-SLAM/third_party/opencv_install/lib:$LD_LIBRARY_PATH

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# =============================================================================
# Parse Arguments
# =============================================================================
SKIP_TRAINING=0
SKIP_EVAL=0
SKIP_MESH_GEN=0
SKIP_MESH_EVAL=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-training)
            SKIP_TRAINING=1
            shift
            ;;
        --skip-eval)
            SKIP_EVAL=1
            shift
            ;;
        --skip-mesh-gen)
            SKIP_MESH_GEN=1
            shift
            ;;
        --skip-mesh-eval)
            SKIP_MESH_EVAL=1
            shift
            ;;
        --iterations)
            ITERATIONS=$2
            shift 2
            ;;
        --start-iter)
            START_ITER=$2
            shift 2
            ;;
        --scenes)
            IFS=',' read -ra SCENES <<< "$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-training     Skip training step (use existing results)"
            echo "  --skip-eval         Skip onekey evaluation step"
            echo "  --skip-mesh-gen     Skip mesh generation step"
            echo "  --skip-mesh-eval    Skip mesh evaluation step"
            echo "  --iterations N      Number of training iterations (default: 5)"
            echo "  --start-iter N      Start iteration index (default: 0)"
            echo "  --scenes S1,S2,...  Comma-separated list of scenes"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Full pipeline"
            echo "  $0 --skip-training           # Only eval & mesh steps"
            echo "  $0 --iterations 3            # Run 3 iterations"
            echo "  $0 --scenes office0,room0    # Only specific scenes"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Functions
# =============================================================================

print_header() {
    echo -e "\n${CYAN}=========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=========================================${NC}\n"
}

print_step() {
    echo -e "${GREEN}[STEP $1/$2] $3${NC}"
}

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

# =============================================================================
# Main Execution
# =============================================================================

print_header "Replica RGB-D PA6 Full Pipeline"
echo "Dataset Path:    $DATASET_PATH"
echo "Result Base:     $RESULT_BASE"
echo "Mesh Output:     $MESH_OUTPUT_DIR"
echo "Iterations:      $ITERATIONS (starting from $START_ITER)"
echo "Scenes:          ${SCENES[*]}"
echo ""

# Create directories
mkdir -p "$RESULT_BASE"
mkdir -p "$MESH_OUTPUT_DIR"

# =============================================================================
# STEP 1: Training
# =============================================================================
if [ $SKIP_TRAINING -eq 0 ]; then
    print_step 1 4 "Running Training (PA6 - L_geo λ=0.2)"
    
    for i in $(seq $START_ITER $((ITERATIONS-1+START_ITER)))
    do
        print_info "=== Iteration $i ==="
        
        for scene in "${SCENES[@]}"
        do
            echo "Processing $scene (RGB-D PA6)..."
            
            ../bin/replica_rgbd \
                ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
                ../cfg/ORB_SLAM3/RGB-D/Replica/${scene}.yaml \
                ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
                ${DATASET_PATH}/Replica/${scene} \
                ${RESULT_BASE}/replica_rgbd_${i}/${scene} \
                no_viewer
            
            echo -e "${GREEN}✓ $scene completed${NC}"
        done
    done
    
    echo -e "${GREEN}Training completed!${NC}"
else
    print_step 1 4 "Skipping Training (--skip-training)"
fi

# =============================================================================
# STEP 2: OneKey Evaluation
# =============================================================================
if [ $SKIP_EVAL -eq 0 ]; then
    print_step 2 4 "Running OneKey Evaluation"
    
    cd ../Photo-SLAM-eval
    python3 onekey.py -d ${DATASET_PATH} -r ${RESULT_BASE}/
    cd "$SCRIPT_DIR"
    
    echo -e "${GREEN}OneKey evaluation completed!${NC}"
    
    # Display summary
    if [ -f "${RESULT_BASE}/log.txt" ]; then
        echo ""
        cat "${RESULT_BASE}/log.txt"
    fi
else
    print_step 2 4 "Skipping OneKey Evaluation (--skip-eval)"
fi

# =============================================================================
# STEP 3: Mesh Generation
# =============================================================================
if [ $SKIP_MESH_GEN -eq 0 ]; then
    print_step 3 4 "Generating TSDF Meshes"
    
    # Activate virtual environment if exists
    if [ -d "tsdf_env" ]; then
        source tsdf_env/bin/activate
    fi
    
    for i in $(seq $START_ITER $((ITERATIONS-1+START_ITER)))
    do
        print_info "=== Mesh Generation - Iteration $i ==="
        
        for scene in "${SCENES[@]}"
        do
            RESULT_DIR="${RESULT_BASE}/replica_rgbd_${i}/${scene}"
            MESH_FILE="${MESH_OUTPUT_DIR}/pa6_${scene}_run${i}.ply"
            
            if [ ! -d "$RESULT_DIR" ]; then
                echo -e "${YELLOW}Warning: Result directory not found: $RESULT_DIR${NC}"
                continue
            fi
            
            echo "Generating mesh for $scene (run $i)..."
            
            # Use CPU-based TSDF mesh generation (more stable than GPU API)
            python3 generate_replica_mesh_gpu.py \
                --result_dir "$RESULT_DIR" \
                --dataset_path "${DATASET_PATH}/Replica/${scene}" \
                --output "$MESH_FILE" \
                --voxel_size $VOXEL_SIZE \
                --sdf_trunc $SDF_TRUNC \
                --depth_scale $DEPTH_SCALE \
                --depth_max $DEPTH_TRUNC \
                --cpu \
                2>/dev/null || {
                    echo -e "${YELLOW}GPU mesh generation failed, trying CPU fallback...${NC}"
                    python3 generate_replica_mesh.py \
                        --result_dir "$RESULT_DIR" \
                        --dataset_path "${DATASET_PATH}/Replica/${scene}" \
                        --output "$MESH_FILE" \
                        --voxel_size $VOXEL_SIZE \
                        --sdf_trunc $SDF_TRUNC \
                        --depth_scale $DEPTH_SCALE \
                        --depth_trunc $DEPTH_TRUNC \
                        2>/dev/null || echo -e "${YELLOW}Mesh generation failed for $scene${NC}"
                }
            
            if [ -f "$MESH_FILE" ]; then
                echo -e "${GREEN}✓ Generated: $MESH_FILE${NC}"
            fi
        done
    done
    
    if [ -d "tsdf_env" ]; then
        deactivate 2>/dev/null || true
    fi
    
    echo -e "${GREEN}Mesh generation completed!${NC}"
else
    print_step 3 4 "Skipping Mesh Generation (--skip-mesh-gen)"
fi

# =============================================================================
# STEP 4: Mesh Evaluation
# =============================================================================
if [ $SKIP_MESH_EVAL -eq 0 ]; then
    print_step 4 4 "Evaluating Meshes"
    
    # Activate virtual environment if exists
    if [ -d "tsdf_env" ]; then
        source tsdf_env/bin/activate
    fi
    
    EVAL_RESULTS_FILE="${MESH_OUTPUT_DIR}/mesh_evaluation_results.json"
    echo "{" > "$EVAL_RESULTS_FILE"
    FIRST=1
    
    for i in $(seq $START_ITER $((ITERATIONS-1+START_ITER)))
    do
        for scene in "${SCENES[@]}"
        do
            PRED_MESH="${MESH_OUTPUT_DIR}/pa6_${scene}_run${i}.ply"
            GT_MESH="${GT_MESH_DIR}/${scene}/mesh.ply"
            
            if [ ! -f "$PRED_MESH" ]; then
                echo -e "${YELLOW}Predicted mesh not found: $PRED_MESH${NC}"
                continue
            fi
            
            if [ ! -f "$GT_MESH" ]; then
                echo -e "${YELLOW}GT mesh not found: $GT_MESH${NC}"
                # Try alternative GT mesh locations
                GT_MESH="${GT_MESH_DIR}/${scene}/habitat/mesh_semantic.ply"
                if [ ! -f "$GT_MESH" ]; then
                    echo -e "${YELLOW}Skipping $scene - no GT mesh found${NC}"
                    continue
                fi
            fi
            
            echo "Evaluating $scene (run $i)..."
            
            OUTPUT_FILE="${MESH_OUTPUT_DIR}/eval_${scene}_run${i}.json"
            
            python3 evaluate_meshes.py \
                --pred "$PRED_MESH" \
                --gt "$GT_MESH" \
                --samples 100000 \
                --output "$OUTPUT_FILE" \
                2>/dev/null || echo -e "${YELLOW}Evaluation failed for $scene${NC}"
            
            if [ -f "$OUTPUT_FILE" ]; then
                echo -e "${GREEN}✓ Evaluation saved: $OUTPUT_FILE${NC}"
            fi
        done
    done
    
    if [ -d "tsdf_env" ]; then
        deactivate 2>/dev/null || true
    fi
    
    echo -e "${GREEN}Mesh evaluation completed!${NC}"
else
    print_step 4 4 "Skipping Mesh Evaluation (--skip-mesh-eval)"
fi

# =============================================================================
# Summary
# =============================================================================
print_header "Pipeline Complete!"

echo "Results saved to:"
echo "  Training results:  $RESULT_BASE/"
echo "  Evaluation logs:   $RESULT_BASE/log.txt, log.csv"
echo "  Generated meshes:  $MESH_OUTPUT_DIR/"
echo "  Mesh evaluations:  $MESH_OUTPUT_DIR/eval_*.json"
echo ""
echo "Quick commands:"
echo "  View results:      cat $RESULT_BASE/log.txt"
echo "  View mesh:         python3 view_mesh.py $MESH_OUTPUT_DIR/pa6_office0_run0.ply"
echo ""
echo -e "${GREEN}Done! 🎉${NC}"
