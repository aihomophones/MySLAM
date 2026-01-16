#!/usr/bin/env python3
"""
Compare PA6 and Baseline meshes against Ground Truth meshes from TUM data.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

try:
    import numpy as np
except ImportError:
    print("Error: numpy not found")
    sys.exit(1)

from evaluate_meshes import evaluate_meshes

# Dataset mapping
DATASET_MAP = {
    'fr1_desk': 'freiburg1_desk_dense.ply',
    'fr2_xyz': 'freiburg2_xyz_dense.ply',
    'fr3_long': 'freiburg3_long_dense.ply'
}

def compare_against_gt():
    """Compare PA6 and Baseline meshes against GT meshes."""
    
    base_path = Path('/media/tam/DATA/3D/CG-photo')
    gt_path = base_path / 'meshes'
    pa6_path = base_path / 'meshes_pa' / 'pa6'
    baseline_path = base_path / 'meshes_pa' / 'baseline'
    output_path = base_path / 'meshes_pa'
    
    print(f"\n{'='*70}")
    print("COMPARISON: PA6 & BASELINE vs GROUND TRUTH")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"GT meshes: {gt_path}")
    
    all_results = []
    
    for ds_short, gt_filename in DATASET_MAP.items():
        gt_mesh = gt_path / gt_filename
        if not gt_mesh.exists():
            print(f"\nWarning: GT mesh not found: {gt_mesh}")
            continue
        
        print(f"\n{'#'*70}")
        print(f"Dataset: {ds_short}")
        print(f"{'#'*70}")
        
        # Find PA6 rendered meshes for this dataset
        pa6_meshes = sorted(pa6_path.glob(f'pa6_{ds_short}_run*_rendered.ply'))
        baseline_meshes = sorted(baseline_path.glob(f'baseline_{ds_short}_run*_gt.ply'))
        
        # Evaluate PA6 meshes
        for mesh in pa6_meshes:
            run = mesh.stem.split('_run')[1].split('_')[0]
            print(f"\n--- PA6 {ds_short} run{run} vs GT ---")
            try:
                results = evaluate_meshes(str(mesh), str(gt_mesh), num_samples=100000)
                all_results.append({
                    'variant': 'PA6',
                    'dataset': ds_short,
                    'run': run,
                    'chamfer': results['chamfer_distance'],
                    'accuracy_cm': results['accuracy_mean'] * 100,
                    'completion_cm': results['completion_mean'] * 100,
                    'f_score_1cm': results['f_scores']['1cm']['f_score'],
                    'f_score_5cm': results['f_scores']['5cm']['f_score'],
                    'f_score_10cm': results['f_scores']['10cm']['f_score'],
                })
            except Exception as e:
                print(f"  Error: {e}")
        
        # Evaluate Baseline meshes
        for mesh in baseline_meshes:
            run = mesh.stem.split('_run')[1].split('_')[0]
            print(f"\n--- Baseline {ds_short} run{run} vs GT ---")
            try:
                results = evaluate_meshes(str(mesh), str(gt_mesh), num_samples=100000)
                all_results.append({
                    'variant': 'Baseline',
                    'dataset': ds_short,
                    'run': run,
                    'chamfer': results['chamfer_distance'],
                    'accuracy_cm': results['accuracy_mean'] * 100,
                    'completion_cm': results['completion_mean'] * 100,
                    'f_score_1cm': results['f_scores']['1cm']['f_score'],
                    'f_score_5cm': results['f_scores']['5cm']['f_score'],
                    'f_score_10cm': results['f_scores']['10cm']['f_score'],
                })
            except Exception as e:
                print(f"  Error: {e}")
    
    # Save results
    if all_results:
        csv_path = output_path / 'pa6_baseline_vs_gt_comparison.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Results saved to: {csv_path}")
        
        # Calculate averages by variant
        for variant in ['PA6', 'Baseline']:
            var_results = [r for r in all_results if r['variant'] == variant]
            if var_results:
                avg_chamfer = np.mean([r['chamfer'] for r in var_results])
                avg_acc = np.mean([r['accuracy_cm'] for r in var_results])
                avg_f5 = np.mean([r['f_score_5cm'] for r in var_results])
                print(f"\n{variant}:")
                print(f"  Avg Chamfer: {avg_chamfer:.4f} m")
                print(f"  Avg Accuracy: {avg_acc:.2f} cm")
                print(f"  Avg F@5cm: {avg_f5*100:.1f}%")
        
        return all_results
    
    return None


if __name__ == '__main__':
    compare_against_gt()
