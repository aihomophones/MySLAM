#!/bin/bash
# PA5 Test: L_geo enabled (lambda_geo=1.0)
# Purpose: Test geometric sensor depth loss with direct RGBD supervision
# Replaces L_align with L_geo for better geometric accuracy

echo "=========================================="
echo "TUM RGB-D Benchmark - PA5 (L_geo)"
echo "=========================================="
echo "L_geo: lambda_geo = 1.0"
echo "L_align: DISABLED"
echo "Iterations: 3 per dataset"
echo "=========================================="
echo ""

for i in 0 1 2 3 4 5 6
do
echo "Iteration $i/2..."

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
    ../results_pa5/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
    ../results_pa5/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
    ../results_pa5/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
    no_viewer

done

echo ""
echo "=========================================="
echo "PA5 Test Complete! Results saved to results_pa5/"
echo "=========================================="
echo "Run evaluation: cd Photo-SLAM-eval && python onekey.py -d /media/tam/DATA/data -r ../results_pa5/"
echo "=========================================="
