#!/bin/bash
# Replica RGB-D Testing Script
# Simplified script for RGB-D testing only

set -e

DATASET_PATH="/media/tam/DATA/data"
ITERATIONS=5

echo "========================================="
echo "Replica RGB-D Testing"
echo "Dataset: ${DATASET_PATH}/Replica"
echo "Iterations: ${ITERATIONS}"
echo "========================================="
echo ""

cd "$(dirname "$0")"

for i in $(seq 0 $((ITERATIONS-1)))
do
    echo "=== Iteration $i/$((ITERATIONS-1)) ==="
    
    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/office0.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/office0 \
        ../results/replica_rgbd_${i}/office0 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/office1.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/office1 \
        ../results/replica_rgbd_${i}/office1 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/office2.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/office2 \
        ../results/replica_rgbd_${i}/office2 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/office3.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/office3 \
        ../results/replica_rgbd_${i}/office3 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/office4.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/office4 \
        ../results/replica_rgbd_${i}/office4 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/room0.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/room0 \
        ../results/replica_rgbd_${i}/room0 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/room1.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/room1 \
        ../results/replica_rgbd_${i}/room1 \
        no_viewer

    ../bin/replica_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/Replica/room2.yaml \
        ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
        ${DATASET_PATH}/Replica/room2 \
        ../results/replica_rgbd_${i}/room2 \
        no_viewer
done

echo ""
echo "========================================="
echo "RGB-D testing completed!"
echo "Results saved in: ../results/replica_rgbd_*/"
echo ""
echo "To evaluate, run:"
echo "  cd ../Photo-SLAM-eval"
echo "  python onekey.py -d ${DATASET_PATH} -r ../results/"
echo "========================================="
