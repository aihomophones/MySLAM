#!/bin/bash
# Quick test to verify depth rendering is working

echo "=========================================="
echo "Testing Depth Rendering"
echo "=========================================="
echo ""
echo "Running PA6 on ONE dataset to test depth saving..."
echo ""

# Modify PA6 script to run only freiburg1_desk for quick test
cd /media/tam/DATA/3D/CG-photo

# Run on freiburg1_desk only
echo "Running freiburg1_desk..."
./bin/tum_rgbd \
    /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk \
    ./ORB-SLAM3/Vocabulary/ORBvoc.txt \
    ./configs/gaussian_mapper/TUM-RGBD/freiburg1_desk.yaml \
    ./gaussian_config_pa6.yaml \
    results_depth_test/freiburg1_desk

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="
echo ""
echo "Check depth maps at:"
echo "results_depth_test/freiburg1_desk/depth/"
echo ""
echo "Files should include:"
echo "  - *_depth.png (16-bit, for TSDF)"
echo "  - *_depth_vis.jpg (visualization)"
echo ""

# Check if depth folder exists
if [ -d "results_depth_test/freiburg1_desk/depth" ]; then
    echo "✅ Depth folder created!"
    echo ""
    echo "Sample depth files:"
    ls -lh results_depth_test/freiburg1_desk/depth/ | head -10
else
    echo "❌ Depth folder not found"
fi
