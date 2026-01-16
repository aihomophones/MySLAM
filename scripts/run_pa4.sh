#!/bin/bash
# PA4 Experiment Runner
# 1. Modify code (lambda_align=0.1, L_iso disabled)
# 2. Build
# 3. Train (5 iterations via tum_rgbd_pa4.sh)
# 4. Evaluate with onekey.py

set -e

echo "========================================="
echo "PA4 Experiment: High L_align, No L_iso"
echo "Config: lambda_align=0.1, lambda_iso=0.0"
echo "========================================="

# 1. Modify gaussian_mapper.cpp
echo "Modifying code..."
sed -i 's/float lambda_align = .*/float lambda_align = 0.1f;   \/\/ PA4/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_var = .*/float lambda_var = 0.0f;/g' src/gaussian_mapper.cpp
sed -i 's/float lambda_iso = .*/float lambda_iso = 0.0f;   \/\/ PA4 DISABLED/g' src/gaussian_mapper.cpp

# 2. Build
echo "Building..."
cd build && make -j$(nproc) > /dev/null 2>&1 && cd ..
echo "Build complete!"

# 3. Train (5 iterations)
echo ""
echo "Starting training..."
cd scripts
./tum_rgbd_pa4.sh
cd ..

# 4. Evaluate
echo ""
echo "Running evaluation with onekey.py..."
cd Photo-SLAM-eval
python onekey.py -d /media/tam/DATA/data -r ../results_pa4/
cd ..

echo ""
echo "========================================="
echo "PA4 Complete!"
echo "Results: results_pa4/"
echo "Logs: Photo-SLAM-eval/results_pa4/log.csv"
echo "========================================="
