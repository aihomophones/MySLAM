#!/usr/bin/env python3
"""
Evaluate Original Photo-SLAM Baseline

This script evaluates the original Photo-SLAM results (without depth loss)
using GT depth for TSDF mesh generation.
"""

import argparse
import json
import csv
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

try:
    import open3d as o3d
    import numpy as np
except ImportError:
    print("Error: open3d not found. Run: source scripts/tsdf_env/bin/activate")
    sys.exit(1)

from evaluate_meshes import evaluate_meshes
from generate_pa_meshes import create_mesh_from_pa_result, TUM_DATASETS, get_tum_intrinsics

DATASET_SHORT = {
    'rgbd_dataset_freiburg1_desk': 'fr1_desk',
    'rgbd_dataset_freiburg2_xyz': 'fr2_xyz', 
    'rgbd_dataset_freiburg3_long_office_household': 'fr3_long'
}


def find_available_runs(results_path: Path) -> list:
    """Find all available run indices."""
    runs = []
    for d in results_path.iterdir():
        if d.is_dir() and d.name.startswith('tum_rgbd_'):
            try:
                run_idx = int(d.name.split('_')[-1])
                for ds in TUM_DATASETS:
                    ds_path = d / ds
                    if ds_path.exists():
                        shutdown_dirs = list(ds_path.glob('*_shutdown'))
                        if shutdown_dirs:
                            runs.append(run_idx)
                            break
            except ValueError:
                continue
    return sorted(set(runs))


def run_baseline_evaluation(results_path: Path, tum_data_path: Path, 
                            output_dir: Path, gt_meshes_dir: Path,
                            voxel_size: float = 0.01):
    """Run evaluation for original Photo-SLAM baseline."""
    
    print(f"\n{'='*70}")
    print(f"BASELINE PHOTO-SLAM EVALUATION")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    runs = find_available_runs(results_path)
    if not runs:
        print(f"Error: No results found")
        return None
    
    print(f"Found {len(runs)} runs: {runs}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results = []
    
    for run_idx in runs:
        print(f"\n{'#'*70}")
        print(f"Run {run_idx}")
        print(f"{'#'*70}")
        
        for dataset_name in TUM_DATASETS:
            ds_short = DATASET_SHORT[dataset_name]
            print(f"\n--- {ds_short} (Run {run_idx}) ---")
            
            # Mesh paths - baseline only uses GT depth
            baseline_mesh = output_dir / f"baseline_{ds_short}_run{run_idx}_gt.ply"
            
            # Use PA6 GT mesh as reference (or generate new one)
            gt_mesh = gt_meshes_dir / f"pa6_{ds_short}_run{run_idx}_gt.ply"
            
            # Generate baseline mesh if not exists
            if not baseline_mesh.exists():
                print(f"  Generating baseline mesh (GT depth)...")
                success = create_mesh_from_pa_result(
                    pa_name="BASELINE",
                    dataset_name=dataset_name,
                    tum_data_path=tum_data_path,
                    pa_result_path=results_path,  # Use results/ folder
                    output_mesh_path=baseline_mesh,
                    voxel_size=voxel_size,
                    run_index=run_idx,
                    use_rendered_depth=False
                )
                if not success:
                    print(f"  Failed to generate baseline mesh")
                    continue
            else:
                print(f"  Baseline mesh exists: {baseline_mesh.name}")
            
            # For baseline, we compare against itself or skip this step
            # Actually for baseline, we just generate the mesh - 
            # comparison will be done separately with PA6
            
            if baseline_mesh.exists():
                # Get mesh stats
                mesh = o3d.io.read_triangle_mesh(str(baseline_mesh))
                print(f"  Mesh stats: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                
                result_row = {
                    'variant': 'BASELINE',
                    'dataset': ds_short,
                    'run': run_idx,
                    'vertices': len(mesh.vertices),
                    'triangles': len(mesh.triangles),
                    'mesh_path': str(baseline_mesh)
                }
                all_results.append(result_row)
    
    # Save CSV
    if all_results:
        csv_path = output_dir / "baseline_meshes_summary.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Total meshes generated: {len(all_results)}")
        print(f"CSV saved: {csv_path}")
        
        return all_results
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Evaluate baseline Photo-SLAM')
    parser.add_argument('--results_path', type=str, 
                        default='/media/tam/DATA/3D/CG-photo/results',
                        help='Path to baseline results')
    parser.add_argument('--data_path', type=str, 
                        default='/media/tam/DATA/data/TUM',
                        help='Path to TUM datasets')
    parser.add_argument('--output_dir', type=str, 
                        default='/media/tam/DATA/3D/CG-photo/meshes_pa/baseline',
                        help='Output directory')
    parser.add_argument('--gt_meshes_dir', type=str,
                        default='/media/tam/DATA/3D/CG-photo/meshes_pa/pa6',
                        help='Directory with PA6 GT meshes for reference')
    parser.add_argument('--voxel_size', type=float, default=0.01)
    
    args = parser.parse_args()
    
    results = run_baseline_evaluation(
        results_path=Path(args.results_path),
        tum_data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
        gt_meshes_dir=Path(args.gt_meshes_dir),
        voxel_size=args.voxel_size
    )
    
    if results:
        print(f"\n✓ Baseline evaluation complete!")
    else:
        print(f"\n✗ Evaluation failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
