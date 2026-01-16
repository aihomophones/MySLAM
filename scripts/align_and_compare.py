#!/usr/bin/env python3
"""
Align and Compare Meshes using ICP alignment.

Usage:
    python3 scripts/align_and_compare.py --pred mesh.ply --gt gt_mesh.ply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import open3d as o3d
    import numpy as np
except ImportError:
    print("Error: open3d not found. Run: source scripts/tsdf_env/bin/activate")
    sys.exit(1)

from evaluate_meshes import evaluate_meshes, sample_points_from_mesh


def align_point_clouds_icp(source_pcd, target_pcd, threshold=0.5, max_iterations=200):
    """Align source point cloud to target using ICP."""
    
    # Initial transformation (identity)
    trans_init = np.eye(4)
    
    # Run point-to-point ICP
    print("Running ICP alignment...")
    reg_result = o3d.pipelines.registration.registration_icp(
        source_pcd, target_pcd, threshold, trans_init,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=max_iterations)
    )
    
    print(f"  ICP fitness: {reg_result.fitness:.4f}")
    print(f"  ICP RMSE: {reg_result.inlier_rmse:.4f}")
    
    return reg_result.transformation


def align_and_compare(pred_mesh_path: str, gt_mesh_path: str, 
                      num_samples: int = 100000, icp_threshold: float = 0.5):
    """Align predicted mesh to GT and evaluate."""
    
    print(f"\n{'='*60}")
    print("ALIGN AND COMPARE")
    print(f"{'='*60}")
    print(f"Predicted: {pred_mesh_path}")
    print(f"GT:        {gt_mesh_path}")
    
    # Load meshes
    print("\nLoading meshes...")
    mesh_pred = o3d.io.read_triangle_mesh(pred_mesh_path)
    mesh_gt = o3d.io.read_triangle_mesh(gt_mesh_path)
    
    print(f"  Pred: {len(mesh_pred.vertices)} vertices")
    print(f"  GT:   {len(mesh_gt.vertices)} vertices")
    
    # Sample point clouds
    print("\nSampling point clouds...")
    pcd_pred = sample_points_from_mesh(mesh_pred, num_samples)
    pcd_gt = sample_points_from_mesh(mesh_gt, num_samples)
    
    # Compute centroids and center point clouds
    pred_center = pcd_pred.get_center()
    gt_center = pcd_gt.get_center()
    
    print(f"\nCentroids:")
    print(f"  Pred: {pred_center}")
    print(f"  GT:   {gt_center}")
    
    # Center both point clouds
    pcd_pred_centered = o3d.geometry.PointCloud(pcd_pred)
    pcd_gt_centered = o3d.geometry.PointCloud(pcd_gt)
    pcd_pred_centered.translate(-pred_center)
    pcd_gt_centered.translate(-gt_center)
    
    # Align using ICP
    transformation = align_point_clouds_icp(pcd_pred_centered, pcd_gt_centered, icp_threshold)
    
    # Apply transformation
    pcd_pred_aligned = o3d.geometry.PointCloud(pcd_pred_centered)
    pcd_pred_aligned.transform(transformation)
    
    # Evaluate after alignment
    print("\n" + "="*60)
    print("RESULTS AFTER ALIGNMENT")
    print("="*60)
    
    # Chamfer distance
    dists1 = np.asarray(pcd_pred_aligned.compute_point_cloud_distance(pcd_gt_centered))
    dists2 = np.asarray(pcd_gt_centered.compute_point_cloud_distance(pcd_pred_aligned))
    
    chamfer = np.mean(dists1) + np.mean(dists2)
    accuracy = np.mean(dists1)
    completion = np.mean(dists2)
    
    # F-scores
    thresholds = [0.01, 0.02, 0.05, 0.1]
    f_scores = {}
    for t in thresholds:
        precision = np.mean(dists1 < t)
        recall = np.mean(dists2 < t)
        if precision + recall > 0:
            f = 2 * precision * recall / (precision + recall)
        else:
            f = 0.0
        f_scores[f'{int(t*100)}cm'] = f
    
    print(f"\nDistance Metrics:")
    print(f"  Chamfer Distance: {chamfer:.4f} m")
    print(f"  Accuracy (Mean):  {accuracy*100:.2f} cm")
    print(f"  Completion (Mean): {completion*100:.2f} cm")
    
    print(f"\nF-Scores:")
    for t, f in f_scores.items():
        print(f"  @{t}: {f*100:.1f}%")
    
    print(f"\n{'='*60}")
    
    return {
        'chamfer': chamfer,
        'accuracy_cm': accuracy * 100,
        'completion_cm': completion * 100,
        'f_scores': f_scores,
        'transformation': transformation
    }


def main():
    parser = argparse.ArgumentParser(description='Align and compare meshes')
    parser.add_argument('--pred', type=str, required=True, help='Predicted mesh path')
    parser.add_argument('--gt', type=str, required=True, help='Ground truth mesh path')
    parser.add_argument('--samples', type=int, default=100000, help='Number of samples')
    parser.add_argument('--icp_threshold', type=float, default=0.5, help='ICP threshold')
    
    args = parser.parse_args()
    
    align_and_compare(args.pred, args.gt, args.samples, args.icp_threshold)


if __name__ == '__main__':
    main()
