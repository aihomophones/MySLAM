#!/bin/bash
# Script to stress test lambda_geo on fr2_xyz

BASE_DIR="/home/crl/lehieu/CG-photo"
CONFIG_TEMPLATE="${BASE_DIR}/cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd_tuned.yaml"
# Ensure we use the 'tuned' config as base but reset other weights
# actually, better to create a fresh temporary config for each run to be safe.

LAMBDA_GEOS=(0.1 0.5)
SCENE="rgbd_dataset_freiburg2_xyz"

echo "Starting Lambda Geo Sweep on ${SCENE}..."

for val in "${LAMBDA_GEOS[@]}"; do
    echo "=============================================="
    echo " Testing lambda_geo = ${val}"
    echo "=============================================="
    
    # Create temp config
    TEMP_CONFIG="${BASE_DIR}/cfg/gaussian_mapper/RGB-D/TUM/tum_rgbd_geo_${val}.yaml"
    cp "$CONFIG_TEMPLATE" "$TEMP_CONFIG"
    
    # Modify config using sed
    # Reset others to 0.0, set geo to val
    sed -i "s/Optimization.lambda_smooth: .*/Optimization.lambda_smooth: 0.0/" "$TEMP_CONFIG"
    sed -i "s/Optimization.lambda_var: .*/Optimization.lambda_var: 0.0/" "$TEMP_CONFIG"
    sed -i "s/Optimization.lambda_iso: .*/Optimization.lambda_iso: 0.0/" "$TEMP_CONFIG"
    sed -i "s/Optimization.lambda_align: .*/Optimization.lambda_align: 0.0/" "$TEMP_CONFIG"
    sed -i "s/Optimization.lambda_geo: .*/Optimization.lambda_geo: ${val}/" "$TEMP_CONFIG"
    
    # Run pipeline
    # We use a custom PA_NAME for each value to differentiate results
    PA_NAME="tum_geo_${val}"
    
    # Clean previous run if exists
    rm -rf "${BASE_DIR}/results_${PA_NAME}/${SCENE}_run1"
    
    # Execute
    CONFIG_FILE="$TEMP_CONFIG" \
    "${BASE_DIR}/scripts/run_full_tum.sh" "$PA_NAME" "$SCENE" 1 test
    
    echo "Finished run for lambda_geo=${val}"
done

echo "Sweep complete."
