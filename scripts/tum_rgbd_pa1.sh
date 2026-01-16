#!/bin/bash
# PA1 Test: Only L_align enabled (lambda_align=0.05)
# Purpose: Test depth alignment loss alone
# NOTE: Before running, update gaussian_mapper.cpp:
#   lambda_align = 0.05f;
#   lambda_var = 0.0f;
#   lambda_iso = 0.0f;

echo "=== PA1 Test: L_align only (lambda=0.05) ==="
echo "Make sure gaussian_mapper.cpp is configured correctly!"
echo ""

for i in 0 1 2
do
../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
    ../results_pa1/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
    ../results_pa1/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
    ../results_pa1/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
    no_viewer
done

echo ""
echo "PA1 Test Complete! Results saved to results_pa1/"
