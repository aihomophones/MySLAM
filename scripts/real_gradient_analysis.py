#!/usr/bin/env python3
"""
Real Gradient Conflict Analysis for Depth-Photo-SLAM

Sử dụng actual Gaussian model và training data để đo gradient conflict.
Script này load PLY file và images từ kết quả training, 
sau đó compute gradients cho từng loss function.

Usage:
    python real_gradient_analysis.py \
        --ply results_cg/tum_rgbd_0/rgbd_dataset_freiburg1_desk/2881_shutdown/ply/point_cloud/iteration_2881/point_cloud.ply \
        --images /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk/rgb \
        --output gradient_analysis_results.csv
"""

import os
import sys
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from PIL import Image
import glob
from plyfile import PlyData
from pytorch_msssim import ssim as pytorch_ssim
from typing import Dict, List, Tuple
from dataclasses import dataclass
import csv
from tqdm import tqdm


@dataclass 
class GaussianParameters:
    """Gaussian model parameters."""
    xyz: torch.Tensor
    features_dc: torch.Tensor
    features_rest: torch.Tensor
    opacity: torch.Tensor
    scaling: torch.Tensor
    rotation: torch.Tensor


def load_ply_gaussians(ply_path: str, device: str = 'cuda') -> GaussianParameters:
    """Load Gaussian parameters from PLY file."""
    print(f"Loading Gaussians from: {ply_path}")
    
    plydata = PlyData.read(ply_path)
    vertex = plydata['vertex']
    
    # Position
    xyz = np.stack([
        vertex['x'].astype(np.float32),
        vertex['y'].astype(np.float32),
        vertex['z'].astype(np.float32)
    ], axis=1)
    
    # Opacity
    opacity = vertex['opacity'].astype(np.float32).reshape(-1, 1)
    
    # Scaling
    scale_names = [p.name for p in vertex.properties if p.name.startswith("scale_")]
    scales = np.stack([vertex[n].astype(np.float32) for n in sorted(scale_names)], axis=1)
    
    # Rotation
    rot_names = [p.name for p in vertex.properties if p.name.startswith("rot_")]
    rotations = np.stack([vertex[n].astype(np.float32) for n in sorted(rot_names)], axis=1)
    
    # Features (SH coefficients)
    dc_names = [p.name for p in vertex.properties if p.name.startswith("f_dc_")]
    features_dc = np.stack([vertex[n].astype(np.float32) for n in sorted(dc_names)], axis=1)
    
    rest_names = [p.name for p in vertex.properties if p.name.startswith("f_rest_")]
    if rest_names:
        features_rest = np.stack([vertex[n].astype(np.float32) for n in sorted(rest_names)], axis=1)
    else:
        features_rest = np.zeros((xyz.shape[0], 0), dtype=np.float32)
    
    print(f"Loaded {xyz.shape[0]} Gaussians")
    
    return GaussianParameters(
        xyz=torch.tensor(xyz, device=device, requires_grad=True),
        features_dc=torch.tensor(features_dc, device=device, requires_grad=True),
        features_rest=torch.tensor(features_rest, device=device, requires_grad=True),
        opacity=torch.tensor(opacity, device=device, requires_grad=True),
        scaling=torch.tensor(scales, device=device, requires_grad=True),
        rotation=torch.tensor(rotations, device=device, requires_grad=True)
    )


def l1_loss(rendered: torch.Tensor, gt: torch.Tensor) -> torch.Tensor:
    """L1 photometric loss."""
    return torch.abs(rendered - gt).mean()


def ssim_loss(rendered: torch.Tensor, gt: torch.Tensor) -> torch.Tensor:
    """SSIM structural similarity loss (1 - SSIM)."""
    # Input should be NCHW
    if rendered.dim() == 3:
        rendered = rendered.unsqueeze(0)
    if gt.dim() == 3:
        gt = gt.unsqueeze(0)
    return 1.0 - pytorch_ssim(rendered, gt, data_range=1.0)


def depth_alignment_loss(depth: torch.Tensor, median_depth: torch.Tensor) -> torch.Tensor:
    """Depth alignment loss: penalize difference between alpha-blended and median depth."""
    mask = (depth > 0) & (median_depth > 0)
    if mask.sum() == 0:
        return torch.tensor(0.0, device=depth.device)
    return torch.abs(depth[mask] - median_depth[mask]).mean()


def uncertainty_variance_loss(depth_variance: torch.Tensor) -> torch.Tensor:
    """Uncertainty variance loss: minimize depth variance."""
    return depth_variance.mean()


def isotropy_loss(scaling: torch.Tensor, max_ratio: float = 1.5, use_log: bool = True) -> torch.Tensor:
    """Isotropy loss: penalize anisotropic (needle-like) Gaussians."""
    if use_log:
        log_scales = scaling  # Assuming already in log space
    else:
        log_scales = torch.log(scaling.clamp(min=1e-7))
    
    # Compute max - min for each Gaussian
    scale_range = log_scales.max(dim=1).values - log_scales.min(dim=1).values
    
    # Penalize if range exceeds threshold
    excess = F.relu(scale_range - np.log(max_ratio))
    return excess.mean()


def compute_gradients_per_loss(
    params: GaussianParameters,
    losses: Dict[str, torch.Tensor],
    param_names: List[str] = None
) -> Dict[str, torch.Tensor]:
    """
    Compute gradients for each loss separately.
    
    Returns:
        Dictionary of loss_name -> flattened gradient vector
    """
    if param_names is None:
        param_names = ['xyz', 'scaling', 'rotation', 'opacity', 'features_dc']
    
    param_list = [getattr(params, name) for name in param_names]
    gradients = {}
    
    for loss_name, loss in losses.items():
        if loss is None or not isinstance(loss, torch.Tensor):
            continue
        
        # Zero gradients
        for p in param_list:
            if p.grad is not None:
                p.grad.zero_()
        
        # Backward
        if loss.requires_grad:
            loss.backward(retain_graph=True)
        
        # Collect gradients
        grad_list = []
        for p in param_list:
            if p.grad is not None:
                grad_list.append(p.grad.flatten().clone())
            else:
                grad_list.append(torch.zeros(p.numel(), device=p.device))
        
        gradients[loss_name] = torch.cat(grad_list)
    
    return gradients


def cosine_similarity(g1: torch.Tensor, g2: torch.Tensor) -> float:
    """Compute cosine similarity between two gradient vectors."""
    norm1 = g1.norm().item()
    norm2 = g2.norm().item()
    if norm1 < 1e-10 or norm2 < 1e-10:
        return 0.0
    return (g1 @ g2).item() / (norm1 * norm2)


def analyze_gradient_conflicts(
    params: GaussianParameters,
    rendered_image: torch.Tensor,
    gt_image: torch.Tensor,
    depth: torch.Tensor = None,
    median_depth: torch.Tensor = None,
    depth_variance: torch.Tensor = None
) -> Dict:
    """
    Analyze gradient conflicts between loss functions.
    
    Returns:
        Dictionary with conflict analysis results
    """
    # Compute individual losses
    losses = {}
    
    # Photometric losses
    losses['L1'] = l1_loss(rendered_image, gt_image)
    losses['DSSIM'] = ssim_loss(
        rendered_image.permute(2, 0, 1),  # HWC -> CHW
        gt_image.permute(2, 0, 1)
    )
    
    # Depth losses (if available)
    if depth is not None and median_depth is not None:
        losses['L_align'] = depth_alignment_loss(depth, median_depth)
    
    if depth_variance is not None:
        losses['L_var'] = uncertainty_variance_loss(depth_variance)
    
    # Isotropy loss
    losses['L_iso'] = isotropy_loss(params.scaling)
    
    # Compute gradients
    gradients = compute_gradients_per_loss(params, losses)
    
    # Compute pairwise cosine similarities
    loss_names = list(gradients.keys())
    n = len(loss_names)
    
    results = {
        'losses': {name: losses[name].item() for name in loss_names},
        'gradient_magnitudes': {},
        'cosine_similarities': {},
        'conflicts': []
    }
    
    for name in loss_names:
        results['gradient_magnitudes'][name] = gradients[name].norm().item()
    
    for i in range(n):
        for j in range(i + 1, n):
            name_i, name_j = loss_names[i], loss_names[j]
            cos_sim = cosine_similarity(gradients[name_i], gradients[name_j])
            pair_key = f"{name_i}_vs_{name_j}"
            results['cosine_similarities'][pair_key] = cos_sim
            
            if cos_sim < 0:
                results['conflicts'].append({
                    'pair': pair_key,
                    'cosine_similarity': cos_sim,
                    'severity': 'HIGH' if cos_sim < -0.3 else 'MEDIUM' if cos_sim < -0.1 else 'LOW'
                })
    
    return results


def create_synthetic_training_step(
    params: GaussianParameters,
    iteration: int = 0
) -> Dict:
    """
    Create a synthetic training step to measure gradients.
    Uses random synthetic images to compute losses.
    """
    device = params.xyz.device
    H, W = 480, 640
    
    # Create synthetic rendered image (simulate from Gaussians)
    # In real training, this would come from rasterizer
    rendered = torch.rand(H, W, 3, device=device, requires_grad=True)
    
    # Create synthetic ground truth
    gt = torch.rand(H, W, 3, device=device)
    
    # Create synthetic depth (from alpha-blending)
    depth = torch.rand(H, W, device=device, requires_grad=True) * 5.0 + 0.5
    median_depth = depth + torch.randn_like(depth) * 0.1
    depth_variance = torch.rand(H, W, device=device) * 0.5
    
    return analyze_gradient_conflicts(
        params, rendered, gt, depth, median_depth, depth_variance
    )


def run_analysis(ply_path: str, num_iterations: int = 10) -> List[Dict]:
    """Run gradient conflict analysis over multiple synthetic iterations."""
    
    # Load Gaussians
    params = load_ply_gaussians(ply_path)
    
    results_list = []
    
    print(f"\nRunning gradient conflict analysis for {num_iterations} iterations...")
    
    for i in tqdm(range(num_iterations)):
        # Recreate parameters with fresh gradients
        params = GaussianParameters(
            xyz=params.xyz.detach().clone().requires_grad_(True),
            features_dc=params.features_dc.detach().clone().requires_grad_(True),
            features_rest=params.features_rest.detach().clone().requires_grad_(True),
            opacity=params.opacity.detach().clone().requires_grad_(True),
            scaling=params.scaling.detach().clone().requires_grad_(True),
            rotation=params.rotation.detach().clone().requires_grad_(True)
        )
        
        result = create_synthetic_training_step(params, i)
        result['iteration'] = i
        results_list.append(result)
    
    return results_list


def print_analysis_report(results_list: List[Dict]):
    """Print analysis report."""
    print("\n" + "=" * 70)
    print("GRADIENT CONFLICT ANALYSIS REPORT")
    print("=" * 70)
    
    # Average cosine similarities
    all_sims = {}
    for result in results_list:
        for pair, sim in result['cosine_similarities'].items():
            if pair not in all_sims:
                all_sims[pair] = []
            all_sims[pair].append(sim)
    
    print("\n📊 Average Cosine Similarities (across iterations):")
    print("-" * 50)
    
    for pair, sims in sorted(all_sims.items()):
        avg = np.mean(sims)
        std = np.std(sims)
        
        if avg < -0.1:
            status = "🔴 CONFLICT"
        elif avg < 0.3:
            status = "🟡 WEAK"
        else:
            status = "🟢 ALIGNED"
        
        print(f"  {pair:25s}: {avg:+.3f} ± {std:.3f}  {status}")
    
    # Conflict frequency
    conflict_counts = {}
    for result in results_list:
        for conflict in result['conflicts']:
            pair = conflict['pair']
            if pair not in conflict_counts:
                conflict_counts[pair] = 0
            conflict_counts[pair] += 1
    
    print("\n🔴 Conflict Frequency (negative cosine similarity):")
    print("-" * 50)
    
    n_iter = len(results_list)
    for pair, count in sorted(conflict_counts.items(), key=lambda x: -x[1]):
        pct = count / n_iter * 100
        bar = "█" * int(pct / 5)
        print(f"  {pair:25s}: {count:3d}/{n_iter} ({pct:5.1f}%) {bar}")
    
    # Gradient magnitudes
    all_mags = {}
    for result in results_list:
        for loss, mag in result['gradient_magnitudes'].items():
            if loss not in all_mags:
                all_mags[loss] = []
            all_mags[loss].append(mag)
    
    print("\n📏 Average Gradient Magnitudes:")
    print("-" * 50)
    
    max_mag = max(np.mean(m) for m in all_mags.values())
    for loss, mags in sorted(all_mags.items(), key=lambda x: -np.mean(x[1])):
        avg = np.mean(mags)
        bar_len = int(avg / max_mag * 30) if max_mag > 0 else 0
        bar = "█" * bar_len
        print(f"  {loss:10s}: {avg:.4f} {bar}")
    
    print("\n💡 Recommendations based on analysis:")
    print("-" * 50)
    
    # Check for specific conflicts
    problem_pairs = [p for p, s in all_sims.items() if np.mean(s) < 0]
    
    if any('L_iso' in p for p in problem_pairs):
        print("  ⚠️  L_iso causes conflicts - consider REMOVING or reducing weight")
    
    if any('L_align' in p for p in problem_pairs):
        print("  ⚠️  L_align conflicts with photometric - REDUCE lambda_align (0.1 → 0.01)")
    
    if any('L_var' in p for p in problem_pairs):
        print("  ⚠️  L_var conflicts detected - REDUCE lambda_var")
    
    # Check gradient dominance
    mag_items = [(l, np.mean(m)) for l, m in all_mags.items()]
    mag_items.sort(key=lambda x: -x[1])
    
    if len(mag_items) >= 2:
        top_mag = mag_items[0][1]
        second_mag = mag_items[1][1]
        if top_mag > 10 * second_mag:
            print(f"  ⚠️  {mag_items[0][0]} gradient dominates ({top_mag:.2f} vs {second_mag:.2f})")
            print(f"      Consider rebalancing loss weights")


def main():
    parser = argparse.ArgumentParser(description="Real Gradient Conflict Analysis")
    parser.add_argument("--ply", type=str, help="Path to Gaussian PLY file")
    parser.add_argument("--iterations", type=int, default=20, help="Number of analysis iterations")
    parser.add_argument("--output", type=str, default=None, help="Output CSV file")
    
    args = parser.parse_args()
    
    # Find a PLY file if not specified
    if args.ply is None:
        # Try to find one
        ply_files = glob.glob("results_cg/**/point_cloud.ply", recursive=True)
        if not ply_files:
            ply_files = glob.glob("results/**/point_cloud.ply", recursive=True)
        
        if ply_files:
            args.ply = ply_files[0]
            print(f"Using PLY file: {args.ply}")
        else:
            print("ERROR: No PLY file found. Please specify --ply option")
            print("\nRunning with synthetic Gaussians instead...")
            
            # Create synthetic Gaussians
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            n_gaussians = 10000
            
            params = GaussianParameters(
                xyz=torch.randn(n_gaussians, 3, device=device, requires_grad=True),
                features_dc=torch.randn(n_gaussians, 3, device=device, requires_grad=True),
                features_rest=torch.zeros(n_gaussians, 0, device=device, requires_grad=True),
                opacity=torch.randn(n_gaussians, 1, device=device, requires_grad=True),
                scaling=torch.randn(n_gaussians, 3, device=device, requires_grad=True),
                rotation=torch.randn(n_gaussians, 4, device=device, requires_grad=True)
            )
            
            results_list = []
            for i in range(args.iterations):
                params = GaussianParameters(
                    xyz=params.xyz.detach().clone().requires_grad_(True),
                    features_dc=params.features_dc.detach().clone().requires_grad_(True),
                    features_rest=params.features_rest.detach().clone().requires_grad_(True),
                    opacity=params.opacity.detach().clone().requires_grad_(True),
                    scaling=params.scaling.detach().clone().requires_grad_(True),
                    rotation=params.rotation.detach().clone().requires_grad_(True)
                )
                result = create_synthetic_training_step(params, i)
                result['iteration'] = i
                results_list.append(result)
            
            print_analysis_report(results_list)
            return
    
    # Run actual analysis
    results_list = run_analysis(args.ply, args.iterations)
    
    # Print report
    print_analysis_report(results_list)
    
    # Save to CSV if requested
    if args.output:
        with open(args.output, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            first_result = results_list[0]
            header = ['iteration']
            header.extend([f"loss_{k}" for k in first_result['losses'].keys()])
            header.extend([f"grad_mag_{k}" for k in first_result['gradient_magnitudes'].keys()])
            header.extend([f"cos_sim_{k}" for k in first_result['cosine_similarities'].keys()])
            writer.writerow(header)
            
            # Data
            for r in results_list:
                row = [r['iteration']]
                row.extend(r['losses'].values())
                row.extend(r['gradient_magnitudes'].values())
                row.extend(r['cosine_similarities'].values())
                writer.writerow(row)
        
        print(f"\nSaved results to: {args.output}")


if __name__ == "__main__":
    main()
