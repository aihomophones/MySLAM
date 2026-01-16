#!/usr/bin/env python3
"""
Full Alignment Comparison: PA6 vs Baseline vs GT

Runs ICP alignment for all meshes and compares against ground truth.
Outputs comprehensive CSV with all results.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

try:
    import open3d as o3d
    import numpy as np
except ImportError:
    print("Error: open3d not found. Run: source scripts/tsdf_env/bin/activate")
    sys.exit(1)

from evaluate_meshes import sample_points_from_mesh

# Dataset mapping
DATASET_MAP = {
    'fr1_desk': 'freiburg1_desk_dense.ply',
    'fr2_xyz': 'freiburg2_xyz_dense.ply',
    'fr3_long': 'freiburg3_long_dense.ply'
}


def align_and_evaluate(pred_mesh_path, gt_mesh_path, num_samples=100000):
    """Align and evaluate a single mesh pair."""
    
    # Load meshes
    mesh_pred = o3d.io.read_triangle_mesh(str(pred_mesh_path))
    mesh_gt = o3d.io.read_triangle_mesh(str(gt_mesh_path))
    
    # Sample point clouds
    pcd_pred = sample_points_from_mesh(mesh_pred, num_samples)
    pcd_gt = sample_points_from_mesh(mesh_gt, num_samples)
    
    # Center point clouds
    pred_center = pcd_pred.get_center()
    gt_center = pcd_gt.get_center()
    
    pcd_pred_centered = o3d.geometry.PointCloud(pcd_pred)
    pcd_gt_centered = o3d.geometry.PointCloud(pcd_gt)
    pcd_pred_centered.translate(-pred_center)
    pcd_gt_centered.translate(-gt_center)
    
    # ICP alignment
    reg_result = o3d.pipelines.registration.registration_icp(
        pcd_pred_centered, pcd_gt_centered, 0.5, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=200)
    )
    
    # Apply transformation
    pcd_pred_aligned = o3d.geometry.PointCloud(pcd_pred_centered)
    pcd_pred_aligned.transform(reg_result.transformation)
    
    # Compute metrics
    dists1 = np.asarray(pcd_pred_aligned.compute_point_cloud_distance(pcd_gt_centered))
    dists2 = np.asarray(pcd_gt_centered.compute_point_cloud_distance(pcd_pred_aligned))
    
    chamfer = np.mean(dists1) + np.mean(dists2)
    accuracy = np.mean(dists1)
    completion = np.mean(dists2)
    
    # F-scores
    f_scores = {}
    for t in [0.01, 0.02, 0.05, 0.1]:
        precision = np.mean(dists1 < t)
        recall = np.mean(dists2 < t)
        f = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        f_scores[f'{int(t*100)}cm'] = f
    
    return {
        'chamfer': chamfer,
        'accuracy_cm': accuracy * 100,
        'completion_cm': completion * 100,
        'icp_fitness': reg_result.fitness,
        'icp_rmse': reg_result.inlier_rmse,
        **{f'f_{k}': v for k, v in f_scores.items()}
    }


def run_full_comparison():
    """Run full comparison for all PA6 and Baseline meshes."""
    
    base_path = Path('/media/tam/DATA/3D/CG-photo')
    gt_path = base_path / 'meshes'
    pa6_path = base_path / 'meshes_pa' / 'pa6'
    baseline_path = base_path / 'meshes_pa' / 'baseline'
    output_path = base_path / 'meshes_pa'
    
    print(f"\n{'='*70}")
    print("FULL ALIGNMENT COMPARISON: PA6 vs BASELINE vs GT")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = []
    
    for ds_short, gt_filename in DATASET_MAP.items():
        gt_mesh = gt_path / gt_filename
        if not gt_mesh.exists():
            print(f"\nWarning: GT mesh not found: {gt_mesh}")
            continue
        
        print(f"\n{'#'*70}")
        print(f"Dataset: {ds_short}")
        print(f"{'#'*70}")
        
        # PA6 rendered meshes
        pa6_meshes = sorted(pa6_path.glob(f'pa6_{ds_short}_run*_rendered.ply'))
        for mesh in pa6_meshes:
            run = mesh.stem.split('_run')[1].split('_')[0]
            print(f"  PA6 {ds_short} run{run}...", end=' ', flush=True)
            try:
                results = align_and_evaluate(mesh, gt_mesh)
                results.update({'variant': 'PA6', 'dataset': ds_short, 'run': int(run)})
                all_results.append(results)
                print(f"Chamfer={results['chamfer']:.3f}m, F@5cm={results['f_5cm']*100:.1f}%")
            except Exception as e:
                print(f"Error: {e}")
        
        # Baseline meshes
        baseline_meshes = sorted(baseline_path.glob(f'baseline_{ds_short}_run*_gt.ply'))
        for mesh in baseline_meshes:
            run = mesh.stem.split('_run')[1].split('_')[0]
            print(f"  Baseline {ds_short} run{run}...", end=' ', flush=True)
            try:
                results = align_and_evaluate(mesh, gt_mesh)
                results.update({'variant': 'Baseline', 'dataset': ds_short, 'run': int(run)})
                all_results.append(results)
                print(f"Chamfer={results['chamfer']:.3f}m, F@5cm={results['f_5cm']*100:.1f}%")
            except Exception as e:
                print(f"Error: {e}")
    
    # Save results
    if all_results:
        # Reorder columns
        columns = ['variant', 'dataset', 'run', 'chamfer', 'accuracy_cm', 'completion_cm',
                   'f_1cm', 'f_2cm', 'f_5cm', 'f_10cm', 'icp_fitness', 'icp_rmse']
        
        csv_path = output_path / 'full_aligned_comparison.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for r in all_results:
                writer.writerow({k: r.get(k, '') for k in columns})
        
        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY (After ICP Alignment)")
        print(f"{'='*70}")
        
        for variant in ['PA6', 'Baseline']:
            var_results = [r for r in all_results if r['variant'] == variant]
            if var_results:
                avg_chamfer = np.mean([r['chamfer'] for r in var_results])
                avg_acc = np.mean([r['accuracy_cm'] for r in var_results])
                avg_f5 = np.mean([r['f_5cm'] for r in var_results])
                avg_f10 = np.mean([r['f_10cm'] for r in var_results])
                
                print(f"\n{variant} ({len(var_results)} meshes):")
                print(f"  Avg Chamfer:  {avg_chamfer:.4f} m")
                print(f"  Avg Accuracy: {avg_acc:.2f} cm")
                print(f"  Avg F@5cm:    {avg_f5*100:.1f}%")
                print(f"  Avg F@10cm:   {avg_f10*100:.1f}%")
        
        # Compare by dataset
        print(f"\n{'='*70}")
        print("BY DATASET")
        print(f"{'='*70}")
        print(f"{'Dataset':<12} {'Variant':<10} {'Chamfer':>10} {'Acc(cm)':>10} {'F@5cm':>10}")
        print("-" * 55)
        
        for ds in ['fr1_desk', 'fr2_xyz', 'fr3_long']:
            for variant in ['PA6', 'Baseline']:
                ds_results = [r for r in all_results if r['dataset'] == ds and r['variant'] == variant]
                if ds_results:
                    avg_chamfer = np.mean([r['chamfer'] for r in ds_results])
                    avg_acc = np.mean([r['accuracy_cm'] for r in ds_results])
                    avg_f5 = np.mean([r['f_5cm'] for r in ds_results])
                    print(f"{ds:<12} {variant:<10} {avg_chamfer:>10.4f} {avg_acc:>10.2f} {avg_f5*100:>10.1f}%")
        
        print(f"\n{'='*70}")
        print(f"Results saved to: {csv_path}")
        print(f"{'='*70}")
        
        return all_results
    
    return None


if __name__ == '__main__':
    run_full_comparison()
