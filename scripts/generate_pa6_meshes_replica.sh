#!/bin/bash
# Generate TSDF meshes for PA6 on full Replica dataset
# Uses GPU-accelerated Open3D

set -e

cd /media/tam/DATA/3D/CG-photo/scripts

# Activate tsdf_env if not already
if [ -d "tsdf_env" ]; then
    source tsdf_env/bin/activate
fi

# Configuration
RESULTS_BASE="/media/tam/DATA/3D/CG-photo/results_replica_pa6"
REPLICA_BASE="/media/tam/DATA/data/Replica"
OUTPUT_BASE="/media/tam/DATA/3D/CG-photo/meshes_replica_pa6"

# Scenes to process
SCENES=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")

# Number of runs
NUM_RUNS=5

echo "========================================"
echo "PA6 Mesh Generation for Replica Dataset"
echo "========================================"
echo "Results: $RESULTS_BASE"
echo "Dataset: $REPLICA_BASE"
echo "Output:  $OUTPUT_BASE"
echo ""

mkdir -p "$OUTPUT_BASE"

for scene in "${SCENES[@]}"; do
    echo "----------------------------------------"
    echo "Processing scene: $scene"
    echo "----------------------------------------"
    
    for run in $(seq 0 $((NUM_RUNS-1))); do
        RESULT_DIR="$RESULTS_BASE/replica_rgbd_$run/$scene"
        DATASET_PATH="$REPLICA_BASE/$scene"
        OUTPUT_DIR="$OUTPUT_BASE/$scene"
        OUTPUT_FILE="$OUTPUT_DIR/mesh_run${run}.ply"
        
        mkdir -p "$OUTPUT_DIR"
        
        if [ ! -d "$RESULT_DIR" ]; then
            echo "  [SKIP] Run $run: Result directory not found"
            continue
        fi
        
        if [ ! -f "$RESULT_DIR/CameraTrajectory_TUM.txt" ]; then
            echo "  [SKIP] Run $run: No trajectory file"
            continue
        fi
        
        if [ -f "$OUTPUT_FILE" ]; then
            echo "  [SKIP] Run $run: Mesh already exists"
            continue
        fi
        
        echo "  [RUN $run] Generating mesh..."
        
        python3 generate_replica_mesh_gpu.py \
            --result_dir "$RESULT_DIR" \
            --dataset_path "$DATASET_PATH" \
            --output "$OUTPUT_FILE" \
            --voxel_size 0.01 \
            --stride 1 \
            --cpu
        
        if [ -f "$OUTPUT_FILE" ]; then
            echo "  [DONE] Run $run: Mesh saved"
        else
            echo "  [FAIL] Run $run: Mesh generation failed"
        fi
    done
done

echo ""
echo "========================================"
echo "Mesh generation complete!"
echo "Output directory: $OUTPUT_BASE"
echo "========================================"

# Summary
echo ""
echo "Generated meshes:"
find "$OUTPUT_BASE" -name "*.ply" -exec ls -lh {} \; 2>/dev/null || true
