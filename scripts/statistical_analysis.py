#!/usr/bin/env python3
"""
Statistical Analysis for Depth-Photo-SLAM experiments
Compare methods using mean, std, and t-test
"""

import os
import glob
import numpy as np
from scipy import stats

def parse_log_csv(log_path):
    """Parse log.csv and extract metrics per scene"""
    results = {}
    current_run = None
    
    with open(log_path, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('scene'):
            continue
        
        if line.startswith('../') or line.startswith('results'):
            current_run = line
            continue
        
        parts = line.split(',')
        if len(parts) >= 5:
            scene = parts[0]
            try:
                psnr = float(parts[3]) if parts[3] != 'None' else None
                ssim = float(parts[4]) if parts[4] != 'None' else None
                lpips = float(parts[5]) if parts[5] != 'None' else None
                ate = float(parts[1]) if parts[1] != 'None' else None
                
                if scene not in results:
                    results[scene] = {'psnr': [], 'ssim': [], 'lpips': [], 'ate': []}
                
                if psnr: results[scene]['psnr'].append(psnr)
                if ssim: results[scene]['ssim'].append(ssim)
                if lpips: results[scene]['lpips'].append(lpips)
                if ate: results[scene]['ate'].append(ate)
            except:
                continue
    
    return results

def compute_stats(values):
    """Compute mean and std"""
    if not values:
        return None, None
    return np.mean(values), np.std(values)

def t_test(a, b):
    """Perform independent t-test"""
    if len(a) < 2 or len(b) < 2:
        return None
    t_stat, p_value = stats.ttest_ind(a, b)
    return p_value

def main():
    base_dir = "/media/tam/DATA/3D/CG-photo"
    
    methods = {
        'PA0 (baseline)': 'results_cg0',
        'PA1 (L_align)': 'results_pa1',
        'PA2 (L_iso)': 'results_pa2',
        'PA3 (combined)': 'results_pa3'
    }
    
    print("=" * 80)
    print("Statistical Analysis: Depth-Photo-SLAM Experiments")
    print("=" * 80)
    
    all_results = {}
    for name, folder in methods.items():
        log_path = os.path.join(base_dir, folder, 'log.csv')
        if os.path.exists(log_path):
            all_results[name] = parse_log_csv(log_path)
        else:
            print(f"Warning: {log_path} not found")
    
    scenes = ['rgbd_dataset_freiburg1_desk', 'rgbd_dataset_freiburg2_xyz', 
              'rgbd_dataset_freiburg3_long_office_household']
    
    for scene in scenes:
        short_name = scene.replace('rgbd_dataset_', '')
        print(f"\n### {short_name}")
        print("-" * 60)
        
        # PSNR comparison
        print("\n**PSNR (mean ± std):**")
        baseline_psnr = None
        for name, results in all_results.items():
            if scene in results and results[scene]['psnr']:
                values = results[scene]['psnr']
                mean, std = compute_stats(values)
                print(f"  {name}: {mean:.2f} ± {std:.2f} (n={len(values)})")
                if 'PA0' in name:
                    baseline_psnr = values
        
        # T-test against baseline
        if baseline_psnr:
            print("\n**T-test vs PA0 (baseline):**")
            for name, results in all_results.items():
                if 'PA0' not in name and scene in results and results[scene]['psnr']:
                    p = t_test(baseline_psnr, results[scene]['psnr'])
                    if p is not None:
                        sig = "✅ Significant" if p < 0.05 else "❌ Not significant"
                        print(f"  {name}: p = {p:.4f} {sig}")
        
        # SSIM comparison
        print("\n**SSIM (mean ± std):**")
        for name, results in all_results.items():
            if scene in results and results[scene]['ssim']:
                values = results[scene]['ssim']
                mean, std = compute_stats(values)
                print(f"  {name}: {mean:.4f} ± {std:.4f}")
        
        # ATE comparison
        print("\n**ATE RMSE (mean ± std):**")
        for name, results in all_results.items():
            if scene in results and results[scene]['ate']:
                values = results[scene]['ate']
                mean, std = compute_stats(values)
                print(f"  {name}: {mean:.4f} ± {std:.4f}")

    print("\n" + "=" * 80)
    print("Conclusion:")
    print("- p < 0.05: Difference is statistically significant")
    print("- p >= 0.05: Difference may be due to random variation")
    print("=" * 80)

if __name__ == "__main__":
    main()
