#!/usr/bin/env python3
"""
Compare Rendered Depth vs Kinect Sensor Depth
Visualize side-by-side to understand the difference

Usage:
    python compare_depth.py --result_dir results_pa2/tum_rgbd_0/rgbd_dataset_freiburg1_desk \
                            --data_dir /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import cv2
from pathlib import Path
import glob


def load_kinect_depth(path, scale_factor=5000.0):
    """Load Kinect depth image (16-bit PNG, scale 5000 = meters)"""
    depth = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if depth is None:
        return None
    return depth.astype(np.float32) / scale_factor


def find_shutdown_dir(result_dir):
    """Find shutdown directory"""
    dirs = [d for d in os.listdir(result_dir) if 'shutdown' in d]
    return os.path.join(result_dir, dirs[0]) if dirs else None


def load_rendered_images(result_dir):
    """Load rendered RGB images from training output"""
    shutdown_dir = find_shutdown_dir(result_dir)
    if not shutdown_dir:
        return None, None
    
    image_dir = os.path.join(result_dir, "image")
    if not os.path.exists(image_dir):
        image_dir = os.path.join(shutdown_dir, "image")
    
    if not os.path.exists(image_dir):
        return None, None
    
    images = sorted(glob.glob(os.path.join(image_dir, "*.png")))
    return images, shutdown_dir


def load_camera_poses(result_dir):
    """Load camera poses from training output"""
    traj_file = os.path.join(result_dir, "CameraTrajectory_TUM.txt")
    if not os.path.exists(traj_file):
        return None
    
    poses = []
    with open(traj_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8:
                ts = float(parts[0])
                poses.append(ts)
    
    return poses


def compare_depth(data_dir, result_dir, output_dir="depth_comparison"):
    """Compare rendered depth with Kinect depth"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Load Kinect depth images
    depth_txt = os.path.join(data_dir, "depth.txt")
    if not os.path.exists(depth_txt):
        print(f"Error: {depth_txt} not found")
        return
    
    # Parse depth associations
    kinect_depths = []
    with open(depth_txt, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                ts = float(parts[0])
                path = os.path.join(data_dir, parts[1])
                kinect_depths.append((ts, path))
    
    # Load RGB images for reference
    rgb_txt = os.path.join(data_dir, "rgb.txt")
    rgb_images = []
    with open(rgb_txt, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                ts = float(parts[0])
                path = os.path.join(data_dir, parts[1])
                rgb_images.append((ts, path))
    
    # Load rendered images
    rendered_images, shutdown_dir = load_rendered_images(result_dir)
    
    # Get sample frames
    sample_indices = [0, len(kinect_depths)//4, len(kinect_depths)//2, 
                      3*len(kinect_depths)//4, len(kinect_depths)-1]
    sample_indices = [i for i in sample_indices if i < len(kinect_depths)]
    
    # Create comparison figure
    n_samples = min(5, len(sample_indices))
    fig, axes = plt.subplots(3, n_samples, figsize=(4*n_samples, 12))
    
    print(f"\nComparing {n_samples} frames...")
    
    depth_errors = []
    
    for col, idx in enumerate(sample_indices[:n_samples]):
        ts, kinect_path = kinect_depths[idx]
        
        # Load Kinect depth
        kinect_depth = load_kinect_depth(kinect_path)
        if kinect_depth is None:
            continue
        
        # Find corresponding RGB
        rgb_path = None
        for rgb_ts, path in rgb_images:
            if abs(rgb_ts - ts) < 0.05:
                rgb_path = path
                break
        
        # Load RGB image
        if rgb_path and os.path.exists(rgb_path):
            rgb = cv2.imread(rgb_path)
            rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
            axes[0, col].imshow(rgb)
        axes[0, col].set_title(f'Frame {idx}\nRGB', fontsize=10)
        axes[0, col].axis('off')
        
        # Show Kinect depth
        kinect_viz = kinect_depth.copy()
        kinect_viz[kinect_depth == 0] = np.nan
        im1 = axes[1, col].imshow(kinect_viz, cmap='viridis', vmin=0, vmax=4)
        axes[1, col].set_title(f'Kinect Depth\nMean: {np.nanmean(kinect_viz):.2f}m', fontsize=10)
        axes[1, col].axis('off')
        
        # Show rendered image (if available)
        if rendered_images and idx < len(rendered_images):
            rendered = cv2.imread(rendered_images[idx])
            if rendered is not None:
                rendered = cv2.cvtColor(rendered, cv2.COLOR_BGR2RGB)
                axes[2, col].imshow(rendered)
                axes[2, col].set_title('Rendered RGB', fontsize=10)
            else:
                axes[2, col].text(0.5, 0.5, 'N/A', ha='center', va='center',
                                 transform=axes[2, col].transAxes)
        else:
            axes[2, col].text(0.5, 0.5, 'Rendered N/A', ha='center', va='center',
                             transform=axes[2, col].transAxes)
        axes[2, col].axis('off')
        
        # Statistics
        valid_mask = kinect_depth > 0
        if np.sum(valid_mask) > 0:
            print(f"Frame {idx}: Kinect depth range [{kinect_depth[valid_mask].min():.2f}, "
                  f"{kinect_depth[valid_mask].max():.2f}] m, "
                  f"mean {kinect_depth[valid_mask].mean():.2f} m")
    
    # Add colorbars
    fig.colorbar(im1, ax=axes[1, :], label='Depth (m)', shrink=0.6, pad=0.02)
    
    plt.suptitle('Depth Comparison: Kinect Sensor vs Rendered', fontsize=14, y=1.02)
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "depth_comparison.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved: {out_path}")
    plt.close()
    
    # Print summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print(f"""
Kinect provides ground truth depth for each frame.
Current implementation only uses:
  - L_align: |rendered_depth - median_depth| (self-supervised)
  - L_iso: Regularizer on Gaussian shapes
  
MISSING: Direct supervision using Kinect depth!

Recommended: Add sensor depth loss
  L_sensor = |rendered_depth - kinect_depth|
""")


def main():
    parser = argparse.ArgumentParser(description="Compare rendered vs Kinect depth")
    parser.add_argument("--data_dir", type=str, 
                        default="/media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk")
    parser.add_argument("--result_dir", type=str,
                        default="results_pa2/tum_rgbd_0/rgbd_dataset_freiburg1_desk")
    parser.add_argument("--output_dir", type=str,
                        default="depth_comparison")
    args = parser.parse_args()
    
    print("="*60)
    print("Rendered vs Kinect Depth Comparison")
    print("="*60)
    
    compare_depth(args.data_dir, args.result_dir, args.output_dir)


if __name__ == "__main__":
    main()
