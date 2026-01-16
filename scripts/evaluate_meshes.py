#!/usr/bin/env python3
"""
Mesh Evaluation Script for Photo-SLAM PA Experiments

Compares rendered depth mesh vs ground truth depth mesh using:
- Chamfer Distance
- Hausdorff Distance  
- F-Score at various thresholds
- Point-to-point accuracy metrics
"""

import open3d as o3d
import numpy as np
import argparse
from pathlib import Path
import json


def sample_points_from_mesh(mesh, num_points=100000):
    """Sample points uniformly from mesh surface."""
    pcd = mesh.sample_points_uniformly(number_of_points=num_points)
    return pcd


def compute_chamfer_distance(pcd1, pcd2):
    """Compute Chamfer distance between two point clouds."""
    # Distance from pcd1 to pcd2
    dists1 = np.asarray(pcd1.compute_point_cloud_distance(pcd2))
    # Distance from pcd2 to pcd1
    dists2 = np.asarray(pcd2.compute_point_cloud_distance(pcd1))
    
    chamfer = np.mean(dists1) + np.mean(dists2)
    return chamfer, np.mean(dists1), np.mean(dists2)


def compute_hausdorff_distance(pcd1, pcd2):
    """Compute Hausdorff distance between two point clouds."""
    dists1 = np.asarray(pcd1.compute_point_cloud_distance(pcd2))
    dists2 = np.asarray(pcd2.compute_point_cloud_distance(pcd1))
    
    hausdorff = max(np.max(dists1), np.max(dists2))
    return hausdorff


def compute_f_score(pcd1, pcd2, threshold):
    """Compute F-score at given threshold."""
    dists1 = np.asarray(pcd1.compute_point_cloud_distance(pcd2))
    dists2 = np.asarray(pcd2.compute_point_cloud_distance(pcd1))
    
    precision = np.mean(dists1 < threshold)
    recall = np.mean(dists2 < threshold)
    
    if precision + recall > 0:
        f_score = 2 * precision * recall / (precision + recall)
    else:
        f_score = 0.0
    
    return f_score, precision, recall


def compute_accuracy_metrics(pcd_pred, pcd_gt):
    """Compute accuracy, completion, and related metrics."""
    dists_pred_to_gt = np.asarray(pcd_pred.compute_point_cloud_distance(pcd_gt))
    dists_gt_to_pred = np.asarray(pcd_gt.compute_point_cloud_distance(pcd_pred))
    
    metrics = {
        'accuracy_mean': np.mean(dists_pred_to_gt),
        'accuracy_median': np.median(dists_pred_to_gt),
        'accuracy_std': np.std(dists_pred_to_gt),
        'accuracy_90_pct': np.percentile(dists_pred_to_gt, 90),
        'completion_mean': np.mean(dists_gt_to_pred),
        'completion_median': np.median(dists_gt_to_pred),
        'completion_std': np.std(dists_gt_to_pred),
        'completion_90_pct': np.percentile(dists_gt_to_pred, 90),
    }
    
    return metrics


def evaluate_meshes(mesh_pred_path, mesh_gt_path, num_samples=100000):
    """Evaluate predicted mesh against ground truth mesh."""
    
    print(f"\n{'='*60}")
    print("MESH EVALUATION")
    print(f"{'='*60}")
    print(f"Predicted: {mesh_pred_path}")
    print(f"GT:        {mesh_gt_path}")
    print(f"Samples:   {num_samples}")
    print(f"{'='*60}\n")
    
    # Load meshes
    print("Loading meshes...")
    mesh_pred = o3d.io.read_triangle_mesh(str(mesh_pred_path))
    mesh_gt = o3d.io.read_triangle_mesh(str(mesh_gt_path))
    
    print(f"  Predicted: {len(mesh_pred.vertices)} vertices, {len(mesh_pred.triangles)} triangles")
    print(f"  GT:        {len(mesh_gt.vertices)} vertices, {len(mesh_gt.triangles)} triangles")
    
    # Sample points
    print("\nSampling points from meshes...")
    pcd_pred = sample_points_from_mesh(mesh_pred, num_samples)
    pcd_gt = sample_points_from_mesh(mesh_gt, num_samples)
    
    # Compute metrics
    print("Computing metrics...")
    
    # Chamfer distance
    chamfer, chamfer_pred, chamfer_gt = compute_chamfer_distance(pcd_pred, pcd_gt)
    
    # Hausdorff distance
    hausdorff = compute_hausdorff_distance(pcd_pred, pcd_gt)
    
    # F-scores at different thresholds (in meters)
    thresholds = [0.01, 0.02, 0.05, 0.1]  # 1cm, 2cm, 5cm, 10cm
    f_scores = {}
    for t in thresholds:
        f, p, r = compute_f_score(pcd_pred, pcd_gt, t)
        f_scores[f'{int(t*100)}cm'] = {'f_score': f, 'precision': p, 'recall': r}
    
    # Accuracy metrics
    accuracy_metrics = compute_accuracy_metrics(pcd_pred, pcd_gt)
    
    # Compile results
    results = {
        'chamfer_distance': chamfer,
        'chamfer_pred_to_gt': chamfer_pred,
        'chamfer_gt_to_pred': chamfer_gt,
        'hausdorff_distance': hausdorff,
        'f_scores': f_scores,
        **accuracy_metrics
    }
    
    # Print results
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"\nDistance Metrics (meters):")
    print(f"  Chamfer Distance:   {chamfer:.6f}")
    print(f"    Pred -> GT:       {chamfer_pred:.6f}")
    print(f"    GT -> Pred:       {chamfer_gt:.6f}")
    print(f"  Hausdorff Distance: {hausdorff:.6f}")
    
    print(f"\nAccuracy (Pred -> GT):")
    print(f"  Mean:   {accuracy_metrics['accuracy_mean']*100:.2f} cm")
    print(f"  Median: {accuracy_metrics['accuracy_median']*100:.2f} cm")
    print(f"  Std:    {accuracy_metrics['accuracy_std']*100:.2f} cm")
    print(f"  90%:    {accuracy_metrics['accuracy_90_pct']*100:.2f} cm")
    
    print(f"\nCompletion (GT -> Pred):")
    print(f"  Mean:   {accuracy_metrics['completion_mean']*100:.2f} cm")
    print(f"  Median: {accuracy_metrics['completion_median']*100:.2f} cm")
    print(f"  Std:    {accuracy_metrics['completion_std']*100:.2f} cm")
    print(f"  90%:    {accuracy_metrics['completion_90_pct']*100:.2f} cm")
    
    print(f"\nF-Scores:")
    for t, scores in f_scores.items():
        print(f"  @{t}: F={scores['f_score']:.4f} (P={scores['precision']:.4f}, R={scores['recall']:.4f})")
    
    print(f"\n{'='*60}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Evaluate mesh quality')
    parser.add_argument('--pred', type=str, required=True, help='Predicted mesh path')
    parser.add_argument('--gt', type=str, required=True, help='Ground truth mesh path')
    parser.add_argument('--samples', type=int, default=100000, help='Number of points to sample')
    parser.add_argument('--output', type=str, help='Output JSON file for results')
    
    args = parser.parse_args()
    
    results = evaluate_meshes(args.pred, args.gt, args.samples)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}")


if __name__ == '__main__':
    main()
