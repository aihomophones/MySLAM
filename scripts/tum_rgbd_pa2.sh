#!/bin/bash
# PA2 Test: Only L_iso enabled (lambda_iso=0.005)
# Purpose: Test isotropy loss for Gaussian shape regularization

for i in 0 1 2
do
../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg1_desk.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg1_desk.txt \
    ../results_pa2/tum_rgbd_$i/rgbd_dataset_freiburg1_desk \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg2_xyz.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg2_xyz \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg2_xyz.txt \
    ../results_pa2/tum_rgbd_$i/rgbd_dataset_freiburg2_xyz \
    no_viewer

../bin/tum_rgbd \
    ../ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ../cfg/ORB_SLAM3/RGB-D/TUM/tum_freiburg3_long_office_household.yaml \
    ../cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd.yaml \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg3_long_office_household \
    ../cfg/ORB_SLAM3/RGB-D/TUM/associations/tum_freiburg3_long_office_household.txt \
    ../results_pa2/tum_rgbd_$i/rgbd_dataset_freiburg3_long_office_household \
    no_viewer
done

echo ""
echo "PA2 Test Complete! Results saved to results_pa2/"
echo "Run evaluation: cd Photo-SLAM-eval && python onekey.py -d /media/tam/DATA/data -r ../results_pa2/"
