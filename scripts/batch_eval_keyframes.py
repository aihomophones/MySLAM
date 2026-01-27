#!/usr/bin/env python3
"""
Batch evaluate individual keyframe point clouds/meshes against GT mesh.
Iterates through 'meshes/compare_color/keyframes/' and runs eval_recon.py.
Aggregates results (Accuracy, Completion).
"""

import argparse
import subprocess
import re
from pathlib import Path
import sys
import numpy as np

def parse_metrics(output_str):
    metrics = {}
    for line in output_str.split('\n'):
        if 'accuracy:' in line:
            metrics['accuracy'] = float(line.split(':')[1].strip())
        elif 'completion:' in line:
            metrics['completion'] = float(line.split(':')[1].strip())
        elif 'completion ratio:' in line:
            metrics['completion_ratio'] = float(line.split(':')[1].strip())
    return metrics

def main():
    parser = argparse.ArgumentParser(description='Batch evaluate keyframes')
    parser.add_argument('--meshes_dir', required=True, help='Directory containing frameXXX folders')
    parser.add_argument('--gt_mesh', required=True, help='Path to GT mesh')
    parser.add_argument('--eval_script', default='eval_recon.py', help='Path to eval script')
    args = parser.parse_args()

    meshes_dir = Path(args.meshes_dir)
    results = []

    # Find all frame folders
    frame_dirs = sorted([d for d in meshes_dir.glob('frame*') if d.is_dir()], 
                        key=lambda x: int(re.search(r'\d+', x.name).group()))

    print(f"Found {len(frame_dirs)} frames to evaluate.")
    print("-" * 60)
    print(f"{'Frame':<10} | {'Acc (cm)':<10} | {'Comp (cm)':<10} | {'Ratio':<10}")
    print("-" * 60)

    for frame_dir in frame_dirs:
        frame_name = frame_dir.name
        fid = int(re.search(r'\d+', frame_name).group())
        
        # Look for rendered mesh
        rendered_mesh = frame_dir / f"{frame_name}_rendered.ply"
        if not rendered_mesh.exists():
            continue

        # Run evaluation
        cmd = [
            sys.executable, args.eval_script,
            '--rec_mesh', str(rendered_mesh),
            '--gt_mesh', args.gt_mesh,
            '-3d'
        ]
        
        try:
            # Capture output
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            metrics = parse_metrics(result.stdout)
            
            if metrics:
                results.append(metrics)
                print(f"{fid:<10} | {metrics.get('accuracy', 0):<10.2f} | {metrics.get('completion', 0):<10.2f} | {metrics.get('completion_ratio', 0):<10.2f}")
            else:
                print(f"{fid:<10} | {'Error parsing':<30}")
                
        except subprocess.CalledProcessError as e:
            print(f"{fid:<10} | {'Error running':<30}")

    if results:
        avg_acc = np.mean([r['accuracy'] for r in results])
        avg_comp = np.mean([r['completion'] for r in results])
        print("-" * 60)
        print(f"{'AVERAGE':<10} | {avg_acc:<10.2f} | {avg_comp:<10.2f} |")
        print("-" * 60)

if __name__ == '__main__':
    main()
