#!/bin/bash
# Unified test script: Run PA1 and PA3 with auto-rebuild and evaluation
# This script automatically modifies gaussian_mapper.cpp, rebuilds, trains, and evaluates

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MAPPER_FILE="$PROJECT_DIR/src/gaussian_mapper.cpp"
BUILD_DIR="$PROJECT_DIR/build"
EVAL_DIR="$PROJECT_DIR/Photo-SLAM-eval"
DATA_DIR="/media/tam/DATA/data"

# Function to update lambda values
update_lambdas() {
    local align=$1
    local var=$2
    local iso=$3
    local comment=$4
    
    echo "Updating lambdas: align=$align, var=$var, iso=$iso"
    
    # Use sed to replace lambda values
    sed -i "s/float lambda_align = [0-9.]*f;/float lambda_align = ${align}f;/" "$MAPPER_FILE"
    sed -i "s/float lambda_var = [0-9.]*f;/float lambda_var = ${var}f;/" "$MAPPER_FILE"
    sed -i "s/float lambda_iso = [0-9.]*f;/float lambda_iso = ${iso}f;/" "$MAPPER_FILE"
    sed -i "s|// PA[0-9]* TEST:.*|// $comment|" "$MAPPER_FILE"
}

# Function to build
build_project() {
    echo "Building project..."
    cd "$BUILD_DIR"
    make -j$(nproc)
    echo "Build complete!"
}

# Function to run training
run_training() {
    local result_dir=$1
    echo "Running training, saving to $result_dir..."
    cd "$SCRIPT_DIR"
    
    for i in 0 1 2; do
        ../bin/tum_rgbd \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
            ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
            $DATA_DIR/TUM/rgbd_dataset_freiburg1_desk \
            ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
            ../$result_dir/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
            no_viewer

        ../bin/tum_rgbd \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
            ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
            $DATA_DIR/TUM/rgbd_dataset_freiburg2_xyz \
            ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
            ../$result_dir/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
            no_viewer

        ../bin/tum_rgbd \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
            ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
            $DATA_DIR/TUM/rgbd_dataset_freiburg3_long_office_household \
            ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
            ../$result_dir/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
            no_viewer
    done
}

# Function to run evaluation
run_eval() {
    local result_dir=$1
    echo "Running evaluation for $result_dir..."
    cd "$EVAL_DIR"
    python onekey.py -d "$DATA_DIR" -r "../$result_dir/"
}

echo "=============================================="
echo "  Unified Test: PA1 + PA3"
echo "=============================================="

# ============== PA1: Only L_align ==============
echo ""
echo ">>> Starting PA1: L_align only (lambda=0.05)"
echo "----------------------------------------------"
update_lambdas "0.05" "0.0" "0.0" "PA1 TEST: Only L_align enabled"
build_project
run_training "results_pa1"
run_eval "results_pa1"

# ============== PA3: L_align + L_iso ==============
echo ""
echo ">>> Starting PA3: L_align + L_iso combined"
echo "----------------------------------------------"
update_lambdas "0.02" "0.0" "0.003" "PA3 TEST: L_align + L_iso combined"
build_project
run_training "results_pa3"
run_eval "results_pa3"

# ============== Summary ==============
echo ""
echo "=============================================="
echo "  All Tests Complete!"
echo "=============================================="
echo "Results saved in:"
echo "  - results_pa1/ (L_align only)"
echo "  - results_pa3/ (L_align + L_iso)"
echo ""
echo "Compare with baseline:"
echo "  python scripts/compare_results.py -b results -m results_pa1 -o comparison_pa1.md"
echo "  python scripts/compare_results.py -b results -m results_pa3 -o comparison_pa3.md"
