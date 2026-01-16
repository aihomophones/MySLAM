#!/usr/bin/env python3
"""
PA Mesh Evaluation Pipeline - All-in-one script

Usage:
    python3 scripts/evaluate_pa_full.py --pa PA6
    
This will:
1. Find all available runs for the PA variant
2. Generate meshes from rendered depth (if not exists)
3. Generate meshes from GT depth (if not exists)  
4. Evaluate all meshes
5. Output results to CSV
"""

import argparse
import json
import csv
import os
import sys
from pathlib import Path
from datetime import datetime

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import open3d as o3d
    import numpy as np
except ImportError:
    print("Error: open3d not found. Run: source scripts/tsdf_env/bin/activate")
    sys.exit(1)

from evaluate_meshes import evaluate_meshes
from generate_pa_meshes import create_mesh_from_pa_result, TUM_DATASETS, get_tum_intrinsics

# Dataset short names
DATASET_SHORT = {
    'rgbd_dataset_freiburg1_desk': 'fr1_desk',
    'rgbd_dataset_freiburg2_xyz': 'fr2_xyz', 
    'rgbd_dataset_freiburg3_long_office_household': 'fr3_long'
}

def find_available_runs(pa_name: str, results_base: Path) -> list:
    """Find all available run indices for a PA variant."""
    pa_results = results_base / f"results_{pa_name.lower()}"
    if not pa_results.exists():
        return []
    
    runs = []
    for d in pa_results.iterdir():
        if d.is_dir() and d.name.startswith('tum_rgbd_'):
            try:
                run_idx = int(d.name.split('_')[-1])
                # Check if has at least one dataset with results
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


def run_full_evaluation(pa_name: str, results_base: Path, tum_data_path: Path, 
                        output_dir: Path, voxel_size: float = 0.01):
    """Run full evaluation pipeline for a PA variant."""
    
    print(f"\n{'='*70}")
    print(f"PA MESH EVALUATION PIPELINE - {pa_name}")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Find available runs
    runs = find_available_runs(pa_name, results_base)
    if not runs:
        print(f"Error: No results found for {pa_name}")
        return None
    
    print(f"Found {len(runs)} runs: {runs}")
    print(f"Datasets: {list(DATASET_SHORT.values())}")
    
    # Prepare output directory
    pa_output_dir = output_dir / pa_name.lower()
    pa_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Results storage
    all_results = []
    
    for run_idx in runs:
        print(f"\n{'#'*70}")
        print(f"Run {run_idx}")
        print(f"{'#'*70}")
        
        pa_result_path = results_base / f"results_{pa_name.lower()}"
        
        for dataset_name in TUM_DATASETS:
            ds_short = DATASET_SHORT[dataset_name]
            print(f"\n--- {ds_short} (Run {run_idx}) ---")
            
            # Mesh paths
            rendered_mesh = pa_output_dir / f"{pa_name.lower()}_{ds_short}_run{run_idx}_rendered.ply"
            gt_mesh = pa_output_dir / f"{pa_name.lower()}_{ds_short}_run{run_idx}_gt.ply"
            
            # Generate rendered depth mesh if not exists
            if not rendered_mesh.exists():
                print(f"  Generating rendered depth mesh...")
                success = create_mesh_from_pa_result(
                    pa_name=pa_name,
                    dataset_name=dataset_name,
                    tum_data_path=tum_data_path,
                    pa_result_path=pa_result_path,
                    output_mesh_path=rendered_mesh,
                    voxel_size=voxel_size,
                    run_index=run_idx,
                    use_rendered_depth=True
                )
                if not success:
                    print(f"  Failed to generate rendered mesh")
                    continue
            else:
                print(f"  Rendered mesh exists: {rendered_mesh.name}")
            
            # Generate GT depth mesh if not exists
            if not gt_mesh.exists():
                print(f"  Generating GT depth mesh...")
                success = create_mesh_from_pa_result(
                    pa_name=pa_name,
                    dataset_name=dataset_name,
                    tum_data_path=tum_data_path,
                    pa_result_path=pa_result_path,
                    output_mesh_path=gt_mesh,
                    voxel_size=voxel_size,
                    run_index=run_idx,
                    use_rendered_depth=False
                )
                if not success:
                    print(f"  Failed to generate GT mesh")
                    continue
            else:
                print(f"  GT mesh exists: {gt_mesh.name}")
            
            # Evaluate if both meshes exist
            if rendered_mesh.exists() and gt_mesh.exists():
                print(f"  Evaluating...")
                try:
                    eval_results = evaluate_meshes(
                        str(rendered_mesh), 
                        str(gt_mesh),
                        num_samples=100000
                    )
                    
                    # Store results
                    result_row = {
                        'pa': pa_name,
                        'dataset': ds_short,
                        'run': run_idx,
                        'chamfer': eval_results['chamfer_distance'],
                        'chamfer_pred_to_gt': eval_results['chamfer_pred_to_gt'],
                        'chamfer_gt_to_pred': eval_results['chamfer_gt_to_pred'],
                        'hausdorff': eval_results['hausdorff_distance'],
                        'accuracy_mean_cm': eval_results['accuracy_mean'] * 100,
                        'accuracy_median_cm': eval_results['accuracy_median'] * 100,
                        'completion_mean_cm': eval_results['completion_mean'] * 100,
                        'completion_median_cm': eval_results['completion_median'] * 100,
                        'f_score_1cm': eval_results['f_scores']['1cm']['f_score'],
                        'f_score_2cm': eval_results['f_scores']['2cm']['f_score'],
                        'f_score_5cm': eval_results['f_scores']['5cm']['f_score'],
                        'f_score_10cm': eval_results['f_scores']['10cm']['f_score'],
                    }
                    all_results.append(result_row)
                    
                    # Save individual JSON
                    json_path = pa_output_dir / f"eval_{ds_short}_run{run_idx}.json"
                    with open(json_path, 'w') as f:
                        json.dump(eval_results, f, indent=2)
                    
                except Exception as e:
                    print(f"  Evaluation failed: {e}")
                    continue
            else:
                print(f"  Skipping evaluation - missing meshes")
    
    # Save CSV summary
    if all_results:
        csv_path = pa_output_dir / f"{pa_name.lower()}_evaluation_summary.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Total evaluations: {len(all_results)}")
        print(f"CSV saved: {csv_path}")
        
        # Print summary table
        print(f"\n{'Dataset':<12} {'Run':<5} {'Chamfer':<10} {'Acc(cm)':<10} {'F@5cm':<10}")
        print("-" * 50)
        for r in all_results:
            print(f"{r['dataset']:<12} {r['run']:<5} {r['chamfer']:<10.4f} {r['accuracy_mean_cm']:<10.2f} {r['f_score_5cm']:<10.4f}")
        
        # Calculate averages
        avg_chamfer = np.mean([r['chamfer'] for r in all_results])
        avg_accuracy = np.mean([r['accuracy_mean_cm'] for r in all_results])
        avg_f5 = np.mean([r['f_score_5cm'] for r in all_results])
        print("-" * 50)
        print(f"{'AVERAGE':<12} {'':<5} {avg_chamfer:<10.4f} {avg_accuracy:<10.2f} {avg_f5:<10.4f}")
        
        return all_results
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Full PA evaluation pipeline')
    parser.add_argument('--pa', type=str, required=True, help='PA variant (e.g., PA6)')
    parser.add_argument('--data_path', type=str, default='/media/tam/DATA/data/TUM',
                        help='Path to TUM datasets')
    parser.add_argument('--results_base', type=str, default='/media/tam/DATA/3D/CG-photo',
                        help='Base path for PA results')
    parser.add_argument('--output_dir', type=str, default='/media/tam/DATA/3D/CG-photo/meshes_pa',
                        help='Output directory for meshes')
    parser.add_argument('--voxel_size', type=float, default=0.01,
                        help='Voxel size for TSDF (default: 0.01m)')
    
    args = parser.parse_args()
    
    results = run_full_evaluation(
        pa_name=args.pa.upper(),
        results_base=Path(args.results_base),
        tum_data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
        voxel_size=args.voxel_size
    )
    
    if results:
        print(f"\n✓ Evaluation complete!")
    else:
        print(f"\n✗ Evaluation failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
