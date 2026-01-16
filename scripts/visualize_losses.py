#!/usr/bin/env python3
"""
Visualize All Loss Components
Auto-detects and plots L1, DSSIM, L_geo/L_align, L_iso, L_var, and total loss

Usage:
    python visualize_losses.py --result_dir results_test/tum_rgbd_0/rgbd_dataset_freiburg1_desk
"""

import os
import argparse
import numpy as np
import matplotlib.pyplot as plt
import csv

def read_csv(csv_path):
    """Read CSV file into dictionary of numpy arrays"""
    data = {}
    headers = []
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            for h in headers:
                data[h] = []
            
            for row in reader:
                if len(row) == len(headers):
                    for i, val in enumerate(row):
                        try:
                            data[headers[i]].append(float(val))
                        except ValueError:
                            data[headers[i]].append(np.nan)
                            
        # Convert to numpy arrays
        for k in data:
            data[k] = np.array(data[k])
            
        return data, headers
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return None, None

def plot_loss_components(csv_path, output_dir="loss_viz"):
    """Plot all loss components from CSV file"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Load CSV
    data, headers = read_csv(csv_path)
    if data is None or len(data.get('iteration', [])) == 0:
        print("No data found")
        return

    iterations = data['iteration']
    print(f"Loaded {len(iterations)} data points")
    print(f"Columns: {headers}")
    
    # Auto-detect which depth loss is available
    depth_loss_col = None
    depth_loss_title = None
    if 'L_geo' in data:
        depth_loss_col = 'L_geo'
        depth_loss_title = 'L_geo (Sensor Depth Loss)'
    elif 'L_align' in data:
        depth_loss_col = 'L_align'
        depth_loss_title = 'L_align (Depth Alignment)'
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Plot each loss component (auto-adapt to available columns)
    loss_configs = [
        ('L1', 'L1 Loss (Photometric)', 'blue'),
        ('DSSIM', 'DSSIM (1-SSIM)', 'green'),
    ]
    
    # Add depth loss if available
    if depth_loss_col:
        loss_configs.append((depth_loss_col, depth_loss_title, 'orange'))
    
    # Add other losses if available
    if 'L_iso' in data:
        loss_configs.append(('L_iso', 'L_iso (Isotropy)', 'purple'))
    if 'L_var' in data:
        loss_configs.append(('L_var', 'L_var (Variance)', 'brown'))
    
    # Always add total last
    loss_configs.append(('total', 'Total Loss', 'red'))
    
    for idx, (col, title, color) in enumerate(loss_configs):
        row, col_idx = divmod(idx, 3)
        ax = axes[row, col_idx]
        
        if col in data:
            values = data[col]
            
            ax.plot(iterations, values, color=color, alpha=0.7, linewidth=1.5)
            
            # Add smoothed line
            if len(values) > 5:
                window = 5
                smooth = np.convolve(values, np.ones(window)/window, mode='valid')
                ax.plot(iterations[window-1:], smooth, color='black', 
                       linewidth=2, linestyle='--', label='Smoothed')
            
            ax.set_xlabel('Iteration')
            ax.set_ylabel('Loss Value')
            ax.set_title(f'{title}\nMean: {np.mean(values):.4f}')
            ax.grid(True, alpha=0.3)
            ax.legend()
        else:
            ax.text(0.5, 0.5, f'{col} not found', ha='center', va='center',
                   transform=ax.transAxes)
    
    # Hide empty subplot
    axes[1, 2].axis('off')
    
    plt.suptitle('Loss Components During Training', fontsize=14)
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "loss_components.png")
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    plt.close()
    
    # Create stacked plot showing relative contributions
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Check which columns are available for stacked plot
    has_l1 = 'L1' in data
    has_dssim = 'DSSIM' in data
    
    if has_l1 and has_dssim:
        # Weighted contributions (approximate)
        l1_weighted = data['L1'] * 0.8
        dssim_weighted = data['DSSIM'] * 0.2
        
        ax.fill_between(iterations, 0, l1_weighted, alpha=0.5, label='L1 (×0.8)', color='blue')
        ax.fill_between(iterations, l1_weighted, l1_weighted + dssim_weighted, 
                       alpha=0.5, label='DSSIM (×0.2)', color='green')
        
        bottom = l1_weighted + dssim_weighted
        
        # Add depth loss if available
        if 'L_geo' in data:
            geo_weighted = data['L_geo'] * 1.0  # lambda_geo = 1.0
            ax.fill_between(iterations, bottom, bottom + geo_weighted,
                           alpha=0.5, label='L_geo (×1.0)', color='orange')
            bottom += geo_weighted
        elif 'L_align' in data:
            align_weighted = data['L_align'] * 0.1  # lambda_align = 0.1
            if np.any(align_weighted > 0):
                ax.fill_between(iterations, bottom, bottom + align_weighted,
                               alpha=0.5, label='L_align (×0.1)', color='orange')
                bottom += align_weighted
        
        # Add L_iso if available
        if 'L_iso' in data:
            iso_weighted = data['L_iso'] * 0.01  # lambda_iso = 0.01
            if np.any(iso_weighted > 0):
                ax.fill_between(iterations, bottom, bottom + iso_weighted,
                               alpha=0.5, label='L_iso (×0.01)', color='purple')
                bottom += iso_weighted
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Weighted Loss Contribution')
        ax.set_title('Stacked Weighted Loss Components')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        out_path2 = os.path.join(output_dir, "loss_stacked.png")
        plt.savefig(out_path2, dpi=150, bbox_inches='tight')
        print(f"Saved: {out_path2}")
        plt.close()
    
    # Print statistics
    print("\n" + "="*60)
    print("Loss Statistics")
    print("="*60)
    for col, title, _ in loss_configs:
        if col in data:
            values = data[col]
            print(f"\n{title}:")
            print(f"  Min: {np.min(values):.6f}")
            print(f"  Max: {np.max(values):.6f}")
            print(f"  Mean: {np.mean(values):.6f}")
            print(f"  Std: {np.std(values):.6f}")
            
            # Trend
            if len(values) > 10:
                first = np.mean(values[:len(values)//3])
                last = np.mean(values[-len(values)//3:])
                trend = "↘ Decreasing" if last < first * 0.95 else "↗ Increasing" if last > first * 1.05 else "→ Stable"
                print(f"  Trend: {trend} ({first:.4f} → {last:.4f})")


def main():
    parser = argparse.ArgumentParser(description="Visualize loss components")
    parser.add_argument("--result_dir", type=str, default=".")
    parser.add_argument("--output_dir", type=str, default="loss_viz")
    args = parser.parse_args()
    
    # Find loss_components.csv
    csv_path = os.path.join(args.result_dir, "loss_components.csv")
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        print("\nTo generate this file, run training with loss logging enabled.")
        return
    
    plot_loss_components(csv_path, args.output_dir)


if __name__ == "__main__":
    main()
