#!/bin/bash
# PA8 Test: L_geo + L_align (Hybrid approach)
# Purpose: Combine sensor depth supervision with internal consistency
# Expected: Fix floaters while maintaining geometric accuracy

echo "=========================================="
echo "TUM RGB-D Benchmark - PA8 (Hybrid)"
echo "=========================================="
echo "L_geo: lambda_geo = 0.15 (sensor depth)"
echo "L_align: lambda_align = 0.05 (floater elimination)"
echo "Iterations: 5 per dataset"
echo "=========================================="
echo ""

for i in 0 1 2 3 4
do
echo "Iteration $i/4..."

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
    ../results_pa8/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
    ../results_pa8/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
    ../results_pa8/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
    no_viewer

done

echo ""
echo "=========================================="
echo "PA8 Test Complete! Results saved to results_pa8/"
echo "=========================================="
echo "Run evaluation: cd Photo-SLAM-eval && python onekey.py -d /media/tam/DATA/data -r ../results_pa8/"
echo "=========================================="
