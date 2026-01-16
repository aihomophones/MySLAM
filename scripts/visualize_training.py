#!/usr/bin/env python3
"""
Training Visualization Script
Visualize loss curves, PSNR, SSIM over training iterations/keyframes
and compare rendered depth vs sensor depth

Usage:
    python visualize_training.py --result_dir results_pa2/tum_rgbd_0/rgbd_dataset_freiburg1_desk
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import glob

def find_shutdown_dir(result_dir):
    """Find the shutdown directory"""
    dirs = [d for d in os.listdir(result_dir) if 'shutdown' in d]
    if dirs:
        return os.path.join(result_dir, dirs[0])
    return None

def load_metric_file(filepath):
    """Load metric file (psnr.txt, dssim.txt, etc.)"""
    if not os.path.exists(filepath):
        return None, None
    
    keyframes = []
    values = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    keyframes.append(int(parts[0]))
                    values.append(float(parts[1]))
                except:
                    continue
    
    return np.array(keyframes), np.array(values)

def plot_training_curves(result_dir, output_dir="training_viz"):
    """Plot PSNR and SSIM curves over keyframes"""
    os.makedirs(output_dir, exist_ok=True)
    
    shutdown_dir = find_shutdown_dir(result_dir)
    if not shutdown_dir:
        print(f"No shutdown dir found in {result_dir}")
        return
    
    # Load metrics
    psnr_file = os.path.join(shutdown_dir, "psnr.txt")
    dssim_file = os.path.join(shutdown_dir, "dssim.txt")
    psnr_gs_file = os.path.join(shutdown_dir, "psnr_gaussian_splatting.txt")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # PSNR curve
    kf, psnr = load_metric_file(psnr_file)
    if psnr is not None:
        axes[0, 0].plot(kf, psnr, 'b-o', markersize=3, label='PSNR')
        axes[0, 0].axhline(y=np.mean(psnr), color='r', linestyle='--', 
                          label=f'Mean: {np.mean(psnr):.2f} dB')
        axes[0, 0].set_xlabel('Keyframe ID')
        axes[0, 0].set_ylabel('PSNR (dB)')
        axes[0, 0].set_title('PSNR over Keyframes')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
    
    # DSSIM curve (1-SSIM)
    kf, dssim = load_metric_file(dssim_file)
    if dssim is not None:
        ssim = dssim  # Actually it stores SSIM not DSSIM based on values
        axes[0, 1].plot(kf, ssim, 'g-o', markersize=3, label='SSIM')
        axes[0, 1].axhline(y=np.mean(ssim), color='r', linestyle='--',
                          label=f'Mean: {np.mean(ssim):.4f}')
        axes[0, 1].set_xlabel('Keyframe ID')
        axes[0, 1].set_ylabel('SSIM')
        axes[0, 1].set_title('SSIM over Keyframes')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
    
    # PSNR histogram
    if psnr is not None:
        axes[1, 0].hist(psnr, bins=20, color='blue', alpha=0.7, edgecolor='black')
        axes[1, 0].axvline(x=np.mean(psnr), color='r', linestyle='--', linewidth=2,
                          label=f'Mean: {np.mean(psnr):.2f}')
        axes[1, 0].axvline(x=np.median(psnr), color='g', linestyle='--', linewidth=2,
                          label=f'Median: {np.median(psnr):.2f}')
        axes[1, 0].set_xlabel('PSNR (dB)')
        axes[1, 0].set_ylabel('Count')
        axes[1, 0].set_title('PSNR Distribution')
        axes[1, 0].legend()
    
    # PSNR moving average (smoothed)
    if psnr is not None and len(psnr) > 5:
        window = 5
        psnr_smooth = np.convolve(psnr, np.ones(window)/window, mode='valid')
        kf_smooth = kf[window-1:]
        axes[1, 1].plot(kf, psnr, 'b-', alpha=0.3, label='Raw PSNR')
        axes[1, 1].plot(kf_smooth, psnr_smooth, 'r-', linewidth=2, 
                       label=f'Moving Avg (window={window})')
        axes[1, 1].set_xlabel('Keyframe ID')
        axes[1, 1].set_ylabel('PSNR (dB)')
        axes[1, 1].set_title('PSNR Trend (Smoothed)')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
    
    plt.suptitle(f'Training Metrics: {Path(result_dir).name}', fontsize=14)
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "training_curves.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    plt.close()
    
    # Print summary stats
    print("\n" + "="*60)
    print("Training Statistics Summary")
    print("="*60)
    if psnr is not None:
        print(f"\nPSNR:")
        print(f"  Min: {np.min(psnr):.2f} dB")
        print(f"  Max: {np.max(psnr):.2f} dB")
        print(f"  Mean: {np.mean(psnr):.2f} dB")
        print(f"  Std: {np.std(psnr):.2f} dB")
        print(f"  Median: {np.median(psnr):.2f} dB")
        
        # Trend analysis
        if len(psnr) > 10:
            first_half = np.mean(psnr[:len(psnr)//2])
            second_half = np.mean(psnr[len(psnr)//2:])
            trend = "↗ Improving" if second_half > first_half else "↘ Degrading"
            print(f"  Trend: {trend} ({first_half:.2f} → {second_half:.2f})")
    
    if dssim is not None:
        print(f"\nSSIM:")
        print(f"  Min: {np.min(ssim):.4f}")
        print(f"  Max: {np.max(ssim):.4f}")
        print(f"  Mean: {np.mean(ssim):.4f}")

def compare_methods(result_dirs, method_names, output_dir="training_viz"):
    """Compare PSNR curves across different methods"""
    os.makedirs(output_dir, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = ['blue', 'red', 'green', 'orange', 'purple']
    
    for i, (result_dir, name) in enumerate(zip(result_dirs, method_names)):
        shutdown_dir = find_shutdown_dir(result_dir)
        if not shutdown_dir:
            continue
        
        psnr_file = os.path.join(shutdown_dir, "psnr.txt")
        kf, psnr = load_metric_file(psnr_file)
        
        if psnr is not None:
            # Smoothed curve
            window = 5
            if len(psnr) > window:
                psnr_smooth = np.convolve(psnr, np.ones(window)/window, mode='valid')
                kf_smooth = kf[window-1:]
                ax.plot(kf_smooth, psnr_smooth, color=colors[i % len(colors)], 
                       linewidth=2, label=f'{name} (mean={np.mean(psnr):.2f})')
    
    ax.set_xlabel('Keyframe ID', fontsize=12)
    ax.set_ylabel('PSNR (dB)', fontsize=12)
    ax.set_title('PSNR Comparison Across Methods', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    out_path = os.path.join(output_dir, "method_comparison.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    plt.close()

def main():
    parser = argparse.ArgumentParser(description="Visualize training metrics")
    parser.add_argument("--result_dir", type=str, 
                        default="results_pa2/tum_rgbd_0/rgbd_dataset_freiburg1_desk",
                        help="Path to result directory")
    parser.add_argument("--output_dir", type=str,
                        default="training_viz",
                        help="Output directory for visualizations")
    parser.add_argument("--compare", action="store_true",
                        help="Compare multiple methods")
    args = parser.parse_args()
    
    print("="*60)
    print("Training Visualization")
    print("="*60)
    
    if args.compare:
        # Compare all methods
        base_dir = "/media/tam/DATA/3D/CG-photo"
        methods = [
            ("results_cg0", "PA0 (baseline)"),
            ("results_pa1", "PA1 (L_align)"),
            ("results_pa2", "PA2 (L_iso)"),
            ("results_pa3", "PA3 (combined)"),
        ]
        
        # For freiburg1_desk
        result_dirs = []
        method_names = []
        for folder, name in methods:
            path = os.path.join(base_dir, folder, "tum_rgbd_0", "rgbd_dataset_freiburg1_desk")
            if os.path.exists(path):
                result_dirs.append(path)
                method_names.append(name)
        
        compare_methods(result_dirs, method_names, args.output_dir)
    else:
        plot_training_curves(args.result_dir, args.output_dir)

if __name__ == "__main__":
    main()
