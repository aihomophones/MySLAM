#!/bin/bash
# Run Replica Training and Evaluation
# Complete workflow: Train -> Evaluate -> Generate Report

set -e

# Configuration
DATASET_PATH="/media/tam/DATA/data"
MODE="rgbd"  # Options: rgbd, mono
ITERATIONS=5
RESULT_DIR="replica_${MODE}"

# Parse command line arguments
while getopts "m:i:r:" opt; do
  case $opt in
    m) MODE=$OPTARG ;;
    i) ITERATIONS=$OPTARG ;;
    r) RESULT_DIR=$OPTARG ;;
    \?) echo "Invalid option -$OPTARG" >&2; exit 1 ;;
  esac
done

echo "========================================="
echo "Replica Test & Evaluation Workflow"
echo "========================================="
echo "Mode:           $MODE"
echo "Iterations:     $ITERATIONS"
echo "Result Dir:     results/$RESULT_DIR"
echo "Dataset Path:   $DATASET_PATH"
echo "========================================="
echo ""

# Step 1: Run training
echo "Step 1/3: Running training..."
cd scripts

if [ "$MODE" == "rgbd" ]; then
    ./replica_rgbd_test.sh
elif [ "$MODE" == "mono" ]; then
    # Modify iteration count if needed
    for i in $(seq 0 $((ITERATIONS-1)))
    do
        echo "=== Iteration $i/$((ITERATIONS-1)) ==="
        
        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/office0.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/office0 \
            ../results/replica_mono_${i}/office0 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/office1.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/office1 \
            ../results/replica_mono_${i}/office1 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/office2.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/office2 \
            ../results/replica_mono_${i}/office2 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/office3.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/office3 \
            ../results/replica_mono_${i}/office3 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/office4.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/office4 \
            ../results/replica_mono_${i}/office4 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/room0.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/room0 \
            ../results/replica_mono_${i}/room0 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/room1.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/room1 \
            ../results/replica_mono_${i}/room1 \
            no_viewer

        ../bin/replica_mono \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/Monocular/Replica/room2.yaml \
            ../cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml \
            ${DATASET_PATH}/Replica/room2 \
            ../results/replica_mono_${i}/room2 \
            no_viewer
    done
fi

cd ..
echo "Training completed!"
echo ""

# Step 2: Run evaluation
echo "Step 2/3: Running evaluation..."
cd Photo-SLAM-eval
python onekey.py -d ${DATASET_PATH} -r ../results/
cd ..
echo "Evaluation completed!"
echo ""

# Step 3: Display results
echo "Step 3/3: Generating summary..."
echo ""
echo "========================================="
echo "RESULTS SUMMARY"
echo "========================================="

# Display log.txt if it exists
if [ -f "results/log.txt" ]; then
    cat results/log.txt
    echo ""
fi

# Display CSV summary
if [ -f "results/log.csv" ]; then
    echo "CSV results saved to: results/log.csv"
    echo ""
    echo "First few lines of CSV:"
    head -n 20 results/log.csv
fi

echo ""
echo "========================================="
echo "Workflow completed successfully!"
echo "========================================="
echo ""
echo "Results location: results/"
echo "  - log.txt       (text summary)"
echo "  - log.csv       (CSV format)"
echo ""
echo "Individual scene results:"
echo "  - results/replica_${MODE}_<iteration>/<scene>/"
