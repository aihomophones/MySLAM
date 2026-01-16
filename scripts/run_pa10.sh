#!/bin/bash
# PA10 Experiment Runner
# Config: lambda_geo=0.5 (higher than PA6's 0.2)

set -e

echo "========================================="
echo "PA10 Experiment: High Sensor Depth"
echo "Config: lambda_geo=0.5"
echo "========================================="

# 1. Modify code
echo "Modifying code..."
sed -i 's/float lambda_geo = .*/float lambda_geo = 0.5f;       \/\/ PA10: Higher/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_align = .*/float lambda_align = 0.0f;     \/\/ PA10: DISABLED/g' src/gaussian_mapper.cpp

# 2. Build
echo "Building..."
cd build && make -j$(nproc) > /dev/null 2>&1 && cd ..
echo "Build complete!"

# 3. Train
echo ""
echo "Starting training..."
cd scripts
./tum_rgbd_pa10.sh
cd ..

# 4. Evaluate
echo ""
echo "Running evaluation..."
cd Photo-SLAM-eval
python onekey.py -d /media/tam/DATA/data -r ../results_pa10/
cd ..

echo ""
echo "========================================="
echo "PA10 Complete!"
echo "Results: results_pa10/"
echo "========================================="
