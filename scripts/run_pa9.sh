#!/bin/bash
# PA9 Experiment Runner
# Config: lambda_geo=0.15, lambda_align=0.0

set -e

echo "========================================="
echo "PA9 Experiment: Reduced Sensor Depth"
echo "Config: lambda_geo=0.15, lambda_align=0.0"
echo "========================================="

# 1. Modify code
echo "Modifying code..."
sed -i 's/float lambda_geo = .*/float lambda_geo = 0.15f;      \/\/ PA9: Reduced/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_align = .*/float lambda_align = 0.0f;     \/\/ PA9: DISABLED/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_var = .*/float lambda_var = 0.0f;/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_iso = .*/float lambda_iso = 0.0f;/g' src/gaussian_mapper.cpp

# 2. Build
echo "Building..."
cd build && make -j$(nproc) > /dev/null 2>&1 && cd ..
echo "Build complete!"

# 3. Train
echo ""
echo "Starting training..."
cd scripts
./tum_rgbd_pa9.sh
cd ..

# 4. Evaluate
echo ""
echo "Running evaluation..."
cd Photo-SLAM-eval
python onekey.py -d /media/tam/DATA/data -r ../results_pa9/
cd ..

echo ""
echo "========================================="
echo "PA9 Complete!"
echo "Results: results_pa9/"
echo "========================================="
