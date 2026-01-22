#!/bin/bash
# Evaluate PA6 meshes against Ground Truth for Replica dataset
# Outputs: JSON results per scene and summary CSV

set -e

cd /media/tam/DATA/3D/CG-photo/scripts

# Activate environment
if [ -d "tsdf_env" ]; then
    source tsdf_env/bin/activate
fi

# Configuration
PA6_MESHES="/media/tam/DATA/3D/CG-photo/meshes_replica_pa6"
GT_MESHES="/media/tam/DATA/data/Replica"
OUTPUT_DIR="/media/tam/DATA/3D/CG-photo/eval_results_pa6"

SCENES=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")
NUM_RUNS=5

echo "========================================"
echo "PA6 Mesh Geometry Evaluation"
echo "========================================"
echo "PA6 Meshes: $PA6_MESHES"
echo "GT Meshes:  $GT_MESHES"
echo "Output:     $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Create summary CSV header
SUMMARY_FILE="$OUTPUT_DIR/summary.csv"
echo "scene,run,chamfer,accuracy_mean,completion_mean,f_score_5cm" > "$SUMMARY_FILE"

for scene in "${SCENES[@]}"; do
    echo "----------------------------------------"
    echo "Evaluating scene: $scene"
    echo "----------------------------------------"
    
    GT_MESH="$GT_MESHES/${scene}_mesh.ply"
    
    if [ ! -f "$GT_MESH" ]; then
        echo "  [SKIP] GT mesh not found: $GT_MESH"
        continue
    fi
    
    mkdir -p "$OUTPUT_DIR/$scene"
    
    for run in $(seq 0 $((NUM_RUNS-1))); do
        PRED_MESH="$PA6_MESHES/$scene/mesh_run${run}.ply"
        OUTPUT_JSON="$OUTPUT_DIR/$scene/eval_run${run}.json"
        
        if [ ! -f "$PRED_MESH" ]; then
            echo "  [SKIP] Run $run: Mesh not found"
            continue
        fi
        
        echo "  [RUN $run] Evaluating..."
        
        python3 evaluate_meshes.py \
            --pred "$PRED_MESH" \
            --gt "$GT_MESH" \
            --samples 100000 \
            --output "$OUTPUT_JSON" 2>&1 | tail -20
        
        # Extract metrics for summary
        if [ -f "$OUTPUT_JSON" ]; then
            chamfer=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print(f\"{d['chamfer_distance']:.6f}\")")
            accuracy=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print(f\"{d['accuracy_mean']*100:.2f}\")")
            completion=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print(f\"{d['completion_mean']*100:.2f}\")")
            f_score=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print(f\"{d['f_scores']['5cm']['f_score']:.4f}\")")
            
            echo "$scene,$run,$chamfer,$accuracy,$completion,$f_score" >> "$SUMMARY_FILE"
        fi
    done
done

echo ""
echo "========================================"
echo "Evaluation complete!"
echo "========================================"
echo ""
echo "Summary:"
cat "$SUMMARY_FILE"
echo ""
echo "Detailed results: $OUTPUT_DIR"
