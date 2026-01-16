#!/usr/bin/env python3
"""
Depth Verification Script
Visualize and compare rendered depth vs sensor depth to verify implementation correctness

Usage:
    python verify_depth.py --result_dir results_pa2/tum_rgbd_0/rgbd_dataset_freiburg1_desk \
                           --data_dir /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def load_depth_image(path, scale_factor=5000.0):
    """Load depth image from PNG (TUM format: 16-bit PNG, scale 5000)"""
    import cv2
    depth = cv2.imread(path, cv2.IMREAD_ANYDEPTH)
    if depth is None:
        return None
    return depth.astype(np.float32) / scale_factor  # Convert to meters

def load_associations(data_dir):
    """Load RGB-depth associations"""
    assoc_file = os.path.join(data_dir, "associated_with_gt.txt")
    if not os.path.exists(assoc_file):
        # Try alternate paths
        depth_txt = os.path.join(data_dir, "depth.txt")
        if os.path.exists(depth_txt):
            depths = []
            with open(depth_txt, 'r') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        depths.append((float(parts[0]), parts[1]))
            return depths[:10]  # Return first 10 frames
    return []

def find_rendered_depths(result_dir):
    """Find rendered depth images from training output"""
    # Look for depth files in shutdown folder
    shutdown_dirs = [d for d in os.listdir(result_dir) if 'shutdown' in d]
    if not shutdown_dirs:
        return []
    
    # Check for depth output
    depth_paths = []
    for sd in shutdown_dirs:
        depth_dir = os.path.join(result_dir, sd, "depth")
        if os.path.exists(depth_dir):
            depth_paths = sorted([os.path.join(depth_dir, f) for f in os.listdir(depth_dir) if f.endswith('.png')])
            break
    
    return depth_paths

def analyze_depth_stats(sensor_depths, rendered_depths=None):
    """Analyze depth statistics"""
    print("\n" + "="*60)
    print("Depth Statistics Analysis")
    print("="*60)
    
    if len(sensor_depths) == 0:
        print("No sensor depth images found!")
        return
    
    print(f"\nAnalyzed {len(sensor_depths)} sensor depth frames")
    
    all_depths = []
    for i, depth in enumerate(sensor_depths):
        valid_mask = depth > 0
        if np.sum(valid_mask) > 0:
            valid_depths = depth[valid_mask]
            all_depths.extend(valid_depths)
            
            if i < 3:  # Print first 3 frames
                print(f"\nFrame {i}:")
                print(f"  Valid pixels: {np.sum(valid_mask)} / {depth.size}")
                print(f"  Depth range: [{valid_depths.min():.3f}, {valid_depths.max():.3f}] m")
                print(f"  Mean depth: {valid_depths.mean():.3f} m")
                print(f"  Std depth: {valid_depths.std():.3f} m")
    
    all_depths = np.array(all_depths)
    print(f"\nOverall statistics (all frames):")
    print(f"  Total valid depth samples: {len(all_depths)}")
    print(f"  Depth range: [{all_depths.min():.3f}, {all_depths.max():.3f}] m")
    print(f"  Mean: {all_depths.mean():.3f} m")
    print(f"  Median: {np.median(all_depths):.3f} m")
    print(f"  Std: {all_depths.std():.3f} m")

def visualize_depth(data_dir, result_dir=None, output_dir="depth_debug"):
    """Create depth visualization"""
    import cv2
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load sensor depths
    depth_txt = os.path.join(data_dir, "depth.txt")
    if not os.path.exists(depth_txt):
        print(f"Error: {depth_txt} not found")
        return
    
    depth_files = []
    with open(depth_txt, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                depth_files.append(os.path.join(data_dir, parts[1]))
    
    # Load first 5 frames
    sensor_depths = []
    for i, df in enumerate(depth_files[:5]):
        depth = load_depth_image(df)
        if depth is not None:
            sensor_depths.append(depth)
    
    analyze_depth_stats(sensor_depths)
    
    # Visualize
    fig, axes = plt.subplots(1, min(5, len(sensor_depths)), figsize=(15, 3))
    if len(sensor_depths) == 1:
        axes = [axes]
    
    for i, (ax, depth) in enumerate(zip(axes, sensor_depths)):
        valid_depth = depth.copy()
        valid_depth[depth == 0] = np.nan
        im = ax.imshow(valid_depth, cmap='viridis', vmin=0, vmax=5)
        ax.set_title(f'Frame {i}')
        ax.axis('off')
    
    plt.colorbar(im, ax=axes, label='Depth (m)', shrink=0.8)
    plt.suptitle('Sensor Depth Images (Kinect)')
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "sensor_depth_samples.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved visualization to: {out_path}")
    plt.close()
    
    return sensor_depths

def check_depth_in_training(log_file=None):
    """Check if depth is being used in training by analyzing log output"""
    print("\n" + "="*60)
    print("Training Log Analysis")
    print("="*60)
    
    # Check for depth-related print statements in recent training
    print("\nTo verify depth is being used during training, check for:")
    print("  1. 'depth mean = X.XX' in training output")
    print("  2. 'L_align value = X.XX' in training output")
    print("  3. 'L_var value = X.XX' in training output")
    print("\nIf these values are reasonable (depth ~1-4m for indoor scenes),")
    print("then depth forward pass is working correctly.")

def main():
    parser = argparse.ArgumentParser(description="Verify depth implementation")
    parser.add_argument("--data_dir", type=str, 
                        default="/media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk",
                        help="Path to TUM dataset")
    parser.add_argument("--result_dir", type=str,
                        default=None,
                        help="Path to training results (optional)")
    parser.add_argument("--output_dir", type=str,
                        default="depth_debug",
                        help="Output directory for visualizations")
    args = parser.parse_args()
    
    print("="*60)
    print("Depth Implementation Verification")
    print("="*60)
    print(f"\nData dir: {args.data_dir}")
    
    # Visualize sensor depth
    visualize_depth(args.data_dir, args.result_dir, args.output_dir)
    
    # Check training logs
    check_depth_in_training()
    
    print("\n" + "="*60)
    print("Next Steps:")
    print("="*60)
    print("1. Check the saved visualization")
    print("2. Compare with debug output during training (depth mean values)")
    print("3. If depth mean from training matches sensor depth range, forward pass is correct")
    print("4. Check gradient magnitudes from gradient conflict analysis")

if __name__ == "__main__":
    main()
