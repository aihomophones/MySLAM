#!/bin/bash
# PA7 Test: L_geo enabled (lambda_geo=0.25)
# Purpose: Push geometric supervision slightly higher to improve ATE
# Expected: ATE < 0.010m while maintaining PSNR > 23.0

echo "=========================================="
echo "TUM RGB-D Benchmark - PA7 (L_geo=0.25)"
echo "=========================================="
echo "L_geo: lambda_geo = 0.25 (increased from 0.2)"
echo "L_align: DISABLED"
echo "Iterations: 3 per dataset"
echo "=========================================="
echo ""

for i in 0 1 2 3 4
do
echo "Iteration $i/2..."

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
    ../results_pa7/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
    ../results_pa7/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
    ../results_pa7/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
    no_viewer

done

echo ""
echo "=========================================="
echo "PA7 Test Complete! Results saved to results_pa7/"
echo "=========================================="
echo "Run evaluation: cd Photo-SLAM-eval && python onekey.py -d /media/tam/DATA/data -r ../results_pa7/"
echo "=========================================="
