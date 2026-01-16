#!/usr/bin/env python3
"""
Loss Magnitude Analysis
Check if depth losses are dominating photometric losses

Based on gradient conflict analysis output from training
"""

import re
import sys

# From training logs (manually extracted typical values)
# These are the actual loss VALUES during training

# Typical values from training debug output:
typical_losses = {
    'L1': 0.08,           # L1 photometric loss
    'DSSIM': 0.2,         # 1 - SSIM (DSSIM)  
    'L_align': 0.035,     # depth alignment loss
    'L_var': 0.04,        # depth variance loss
    'L_iso': 0.15,        # isotropy loss
}

# Current weights
weights_pa0 = {'L1': 0.8, 'DSSIM': 0.2, 'L_align': 0.0, 'L_var': 0.0, 'L_iso': 0.0}
weights_pa1 = {'L1': 0.8, 'DSSIM': 0.2, 'L_align': 0.05, 'L_var': 0.0, 'L_iso': 0.0}
weights_pa2 = {'L1': 0.8, 'DSSIM': 0.2, 'L_align': 0.0, 'L_var': 0.0, 'L_iso': 0.005}
weights_pa3 = {'L1': 0.8, 'DSSIM': 0.2, 'L_align': 0.02, 'L_var': 0.0, 'L_iso': 0.003}

def compute_weighted_loss(losses, weights):
    """Compute total weighted loss contribution from each term"""
    contributions = {}
    total = 0.0
    
    for name, value in losses.items():
        weight = weights.get(name, 0.0)
        contrib = value * weight
        contributions[name] = contrib
        total += contrib
    
    return contributions, total

def analyze():
    print("="*70)
    print("Loss Magnitude Analysis")
    print("="*70)
    
    print("\n## Raw Loss Values (typical during training):")
    for name, value in typical_losses.items():
        print(f"  {name}: {value:.4f}")
    
    configs = [
        ("PA0 (baseline)", weights_pa0),
        ("PA1 (L_align)", weights_pa1),
        ("PA2 (L_iso)", weights_pa2),
        ("PA3 (combined)", weights_pa3),
    ]
    
    for config_name, weights in configs:
        print(f"\n## {config_name}")
        print("-"*50)
        
        contributions, total = compute_weighted_loss(typical_losses, weights)
        
        print("Weighted contributions:")
        for name, contrib in contributions.items():
            if contrib > 0:
                pct = 100 * contrib / total if total > 0 else 0
                print(f"  {name:12s}: {contrib:.6f} ({pct:5.1f}%)")
        
        print(f"  {'TOTAL':12s}: {total:.6f}")
        
        # Check if depth losses dominate
        photo_contrib = contributions['L1'] + contributions['DSSIM']
        depth_contrib = contributions['L_align'] + contributions['L_var'] + contributions['L_iso']
        
        if depth_contrib > 0:
            ratio = depth_contrib / photo_contrib * 100
            print(f"\n  Depth/Photometric ratio: {ratio:.1f}%")
            if ratio > 20:
                print("  ⚠️ WARNING: Depth losses may be too dominant!")
            else:
                print("  ✅ Balance looks reasonable")
    
    print("\n" + "="*70)
    print("RECOMMENDATIONS:")
    print("="*70)
    print("""
If depth losses are dominating (>20% of total loss), try:
1. Reduce depth loss weights by 10x
2. Current PA2 has L_iso = 0.005 → try 0.0005
3. Current PA1 has L_align = 0.05 → try 0.005

The goal is depth losses should be <10% of total loss to 
avoid interfering with photometric reconstruction.
""")

if __name__ == "__main__":
    analyze()
