#!/bin/bash

# PA6 Replica Test Script - Lambda Depth = 0
# Run 3 times on all 8 scenes
# Dataset path: /home/crl/lehieu/MyPhotoSLAM/data/Replica

DATASET_DIR="/home/crl/lehieu/MyPhotoSLAM/data/Replica"
RESULT_DIR="../results_replica_pa6_lambda00"

cd "$(dirname "$0")"

for i in 0
do
    echo "=========================================="
    echo "Run $i / 3 (Lambda Depth = 0)"
    echo "=========================================="
    
    # for scene in office0 office1 office2 office3 office4 room0 room1 room2
    for scene in office1
    do
        echo "Processing $scene..."
        ../bin/replica_rgbd \
            ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
            ../cfg/ORB_SLAM3/RGB-D/Replica/${scene}.yaml \
            ../cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml \
            ${DATASET_DIR}/${scene} \
            ${RESULT_DIR}/replica_rgbd_${i}/${scene} \
            no_viewer
    done
done

echo "All runs complete!"
