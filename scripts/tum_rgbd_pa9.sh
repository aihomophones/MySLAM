#!/bin/bash
# PA9: Reduced sensor depth weight (lambda_geo=0.15)
# Testing if lower weight performs better than PA6 (0.2)

set -e

echo "Running PA9 training on 3 TUM datasets (5 iterations each)..."

for i in 0 1 2 3 4
do
    echo ""
    echo "========================================="
    echo "Iteration $i/4"
    echo "========================================="
    
    if [ $i -gt 0 ]; then
        echo "Waiting 5 seconds before next iteration..."
        sleep 5
    fi
    
    # freiburg1_desk
    echo "Training freiburg1_desk..."
    ../bin/tum_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
        ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
        /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
        ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
        ../results_pa9/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
        no_viewer
    
    sleep 3
    
    # freiburg2_xyz
    echo "Training freiburg2_xyz..."
    ../bin/tum_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
        ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
        /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
        ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
        ../results_pa9/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
        no_viewer
    
    sleep 3
    
    # freiburg3_long_office_household
    echo "Training freiburg3_long_office_household..."
    ../bin/tum_rgbd \
        ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
        ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
        ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
        /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
        ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
        ../results_pa9/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
        no_viewer
    
    echo "Iteration $i complete (all 3 datasets)!"
done

echo ""
echo "All training complete! (3 datasets × 5 iterations = 15 runs)"
