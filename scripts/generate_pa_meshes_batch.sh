#!/bin/bash
# Batch script to generate TSDF meshes for all PA experiments

set -e

echo "========================================"
echo "Photo-SLAM PA Mesh Generation Batch"
echo "========================================"

# Activate virtual environment
echo "Activating TSDF environment..."
cd "$(dirname "$0")"
source tsdf_env/bin/activate

# Configuration
DATA_PATH="/media/tam/DATA/data/TUM"
RESULTS_BASE="/media/tam/DATA/3D/CG-photo"
OUTPUT_DIR="/media/tam/DATA/3D/CG-photo/meshes_pa"

# Default: Standard quality (1cm voxels)
VOXEL_SIZE=0.01
SDF_TRUNC=0.04
STRIDE=1
RUN_INDEX=0

# Parse arguments
QUALITY="standard"
PA_FILTER=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --high-quality)
            QUALITY="high"
            VOXEL_SIZE=0.005
            SDF_TRUNC=0.02
            shift
            ;;
        --low-quality)
            QUALITY="low"
            VOXEL_SIZE=0.02
            SDF_TRUNC=0.08
            STRIDE=2
            shift
            ;;
        --pa)
            PA_FILTER="$2"
            shift 2
            ;;
        --run)
            RUN_INDEX="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --high-quality    Generate high quality meshes (5mm voxels, slower)"
            echo "  --low-quality     Generate low quality meshes (2cm voxels, faster)"
            echo "  --pa <PA_NAME>    Generate meshes for specific PA (e.g., PA6)"
            echo "  --run <INDEX>     Use specific run index (0-9, default: 0)"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                          # Standard quality, all PAs"
            echo "  $0 --high-quality           # High quality, all PAs"
            echo "  $0 --pa PA6                 # Standard quality, PA6 only"
            echo "  $0 --high-quality --pa PA6  # High quality, PA6 only"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo ""
echo "Configuration:"
echo "  Quality: $QUALITY"
echo "  Voxel size: ${VOXEL_SIZE}m"
echo "  SDF truncation: ${SDF_TRUNC}m"
echo "  Stride: $STRIDE"
echo "  Run index: $RUN_INDEX"
echo "  Data path: $DATA_PATH"
echo "  Results base: $RESULTS_BASE"
echo "  Output dir: $OUTPUT_DIR"

if [ -n "$PA_FILTER" ]; then
    echo "  PA filter: $PA_FILTER"
fi

echo ""
echo "========================================"

# Check if script exists
if [ ! -f "generate_pa_meshes.py" ]; then
    echo "Error: generate_pa_meshes.py not found!"
    exit 1
fi

# Run mesh generation
echo ""
echo "Starting mesh generation..."
echo ""

if [ -n "$PA_FILTER" ]; then
    # Generate for specific PA
    python3 generate_pa_meshes.py \
        --pa "$PA_FILTER" \
        --data_path "$DATA_PATH" \
        --results_base "$RESULTS_BASE" \
        --output_dir "$OUTPUT_DIR" \
        --voxel_size "$VOXEL_SIZE" \
        --sdf_trunc "$SDF_TRUNC" \
        --stride "$STRIDE" \
        --run_index "$RUN_INDEX" \
        --verbose
else
    # Generate for all PAs
    python3 generate_pa_meshes.py \
        --all \
        --data_path "$DATA_PATH" \
        --results_base "$RESULTS_BASE" \
        --output_dir "$OUTPUT_DIR" \
        --voxel_size "$VOXEL_SIZE" \
        --sdf_trunc "$SDF_TRUNC" \
        --stride "$STRIDE" \
        --run_index "$RUN_INDEX" \
        --verbose
fi

echo ""
echo "========================================"
echo "Mesh generation complete!"
echo "Output directory: $OUTPUT_DIR"
echo "========================================"

# Create README for meshes
README_FILE="$OUTPUT_DIR/README.md"
if [ ! -f "$README_FILE" ]; then
    echo "Creating README..."
    cat > "$README_FILE" << 'EOF'
# Photo-SLAM PA Experiment Meshes

TSDF meshes generated from estimated camera trajectories for all PA experiments.

## Directory Structure

```
meshes_pa/
├── pa1/          # PA1: L_align only
├── pa3/          # PA3: L_align + L_iso
├── pa4/          # PA4: L_align (iso disabled)
├── pa5/          # PA5: L_sensor λ=1.0
├── pa6/          # PA6: L_sensor λ=0.2 ⭐BEST
├── pa7/          # PA7: L_sensor λ=0.25
├── pa8/          # PA8: L_sensor + L_align
├── pa9/          # PA9: L_sensor λ=0.15
└── pa10/         # PA10: L_sensor λ=0.5
```

## Mesh Files

Each PA directory contains meshes for 3 TUM datasets:
- `pa*_fr1_desk_run0.ply` - Freiburg1 Desk
- `pa*_fr2_xyz_run0.ply` - Freiburg2 XYZ
- `pa*_fr3_long_run0.ply` - Freiburg3 Long Office

## Usage

### Evaluation
Compare these meshes with ground truth TSDF meshes in `meshes/` directory:
```bash
python scripts/evaluate_meshes.py \
    --gt meshes/freiburg1_desk_dense.ply \
    --pred meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

### Visualization
```bash
python scripts/view_mesh.py meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

### Analysis
```bash
python scripts/analyze_mesh.py meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

## Generation Settings

See individual PA directories for specific generation parameters.

Standard quality:
- Voxel size: 0.01m (1cm)
- SDF truncation: 0.04m
- Stride: 1 (all frames)

High quality:
- Voxel size: 0.005m (5mm)
- SDF truncation: 0.02m
- Stride: 1 (all frames)

## Regenerate Meshes

```bash
# Standard quality, all PAs
./scripts/generate_pa_meshes_batch.sh

# High quality, all PAs
./scripts/generate_pa_meshes_batch.sh --high-quality

# Specific PA only
./scripts/generate_pa_meshes_batch.sh --pa PA6
```
EOF
    echo "README created: $README_FILE"
fi

echo ""
echo "Done! 🎉"
