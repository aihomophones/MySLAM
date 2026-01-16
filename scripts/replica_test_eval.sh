#!/bin/bash
# Replica Dataset Testing and Evaluation Script
# This script runs Photo-SLAM on Replica dataset and evaluates the results

set -e

# Configuration
DATASET_PATH="/media/tam/DATA/data"
ITERATIONS=5  # Number of iterations to run

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Replica Dataset Test & Evaluation"
echo "========================================="
echo ""

# Function to run RGB-D tests
run_rgbd_tests() {
    echo -e "${GREEN}Running RGB-D tests...${NC}"
    cd ../scripts
    
    for i in $(seq 0 $((ITERATIONS-1)))
    do
        echo -e "${YELLOW}Iteration $i/$((ITERATIONS-1))${NC}"
        
        # All Replica scenes
        scenes=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")
        
        for scene in "${scenes[@]}"
        do
            echo "Processing $scene (RGB-D)..."
            ../bin/replica_rgbd \
                ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
                ../cfg/ORB_SLAM3/RGB-D/Replica/${scene}.yaml \
                ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
                ${DATASET_PATH}/Replica/${scene} \
                ../results/replica_rgbd_${i}/${scene} \
                no_viewer
        done
    done
    
    cd ..
    echo -e "${GREEN}RGB-D tests completed!${NC}"
    echo ""
}

# Function to run Monocular tests
run_mono_tests() {
    echo -e "${GREEN}Running Monocular tests...${NC}"
    cd ../scripts
    
    for i in $(seq 0 $((ITERATIONS-1)))
    do
        echo -e "${YELLOW}Iteration $i/$((ITERATIONS-1))${NC}"
        
        # All Replica scenes
        scenes=("office0" "office1" "office2" "office3" "office4" "room0" "room1" "room2")
        
        for scene in "${scenes[@]}"
        do
            echo "Processing $scene (Monocular)..."
            ../bin/replica_mono \
                ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
                ../cfg/ORB_SLAM3/Monocular/Replica/${scene}.yaml \
                ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
                ${DATASET_PATH}/Replica/${scene} \
                ../results/replica_mono_${i}/${scene} \
                no_viewer
        done
    done
    
    cd ..
    echo -e "${GREEN}Monocular tests completed!${NC}"
    echo ""
}

# Function to run evaluation
run_evaluation() {
    local mode=$1
    echo -e "${GREEN}Running evaluation for ${mode}...${NC}"
    
    cd Photo-SLAM-eval
    python onekey.py -d ${DATASET_PATH} -r ../results/replica_${mode}_*/
    cd ..
    
    echo -e "${GREEN}Evaluation completed!${NC}"
    echo ""
}

# Function to display results summary
display_summary() {
    local mode=$1
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}Results Summary for ${mode}${NC}"
    echo -e "${GREEN}=========================================${NC}"
    
    # Find all result directories for this mode
    for i in $(seq 0 $((ITERATIONS-1)))
    do
        result_dir="../results/replica_${mode}_${i}"
        if [ -f "${result_dir}/log.txt" ]; then
            echo -e "${YELLOW}Iteration $i results:${NC}"
            cat "${result_dir}/log.txt"
            echo ""
        fi
    done
}

# Main execution
MODE="both"  # Options: rgbd, mono, both

if [ $# -gt 0 ]; then
    MODE=$1
fi

echo "Mode: $MODE"
echo "Iterations: $ITERATIONS"
echo "Dataset path: $DATASET_PATH"
echo ""

case $MODE in
    rgbd)
        run_rgbd_tests
        run_evaluation "rgbd"
        display_summary "rgbd"
        ;;
    mono)
        run_mono_tests
        run_evaluation "mono"
        display_summary "mono"
        ;;
    both)
        run_rgbd_tests
        run_mono_tests
        run_evaluation "rgbd"
        run_evaluation "mono"
        display_summary "rgbd"
        display_summary "mono"
        ;;
    *)
        echo -e "${RED}Invalid mode: $MODE${NC}"
        echo "Usage: $0 [rgbd|mono|both]"
        exit 1
        ;;
esac

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}All operations completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Results saved in:"
echo "  - results/replica_rgbd_*/ (RGB-D mode)"
echo "  - results/replica_mono_*/ (Monocular mode)"
echo ""
echo "Log files:"
echo "  - results/replica_rgbd_*/log.csv"
echo "  - results/replica_mono_*/log.csv"
