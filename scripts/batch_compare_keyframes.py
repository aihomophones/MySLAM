#!/usr/bin/env python3
"""
Batch generate meshes for ALL keyframes found in the specific 'depth' directory.
This wraps compare_single_frame_mesh.py.
"""

import argparse
import subprocess
from pathlib import Path
import re
import sys

def main():
    parser = argparse.ArgumentParser(description='Batch generate keyframe meshes')
    parser.add_argument('--result_dir', required=True, help='Photo-SLAM result dir containing .../depth/')
    parser.add_argument('--gt_depth_dir', required=True)
    parser.add_argument('--gt_traj', required=True)
    parser.add_argument('--output_dir', required=True)
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    # Find depth folder
    depth_dirs = list(result_dir.glob('*_shutdown/depth'))
    if not depth_dirs:
        print(f"Error: No depth folder found in {result_dir}")
        sys.exit(1)
    
    depth_dir = depth_dirs[0]
    print(f"Found depth dir: {depth_dir}")

    # Load Keyframe Trajectory mapping (Keyframe Index -> Timestamp)
    # File format: timestamp tx ty tz qx qy qz qw
    traj_file = result_dir / "KeyFrameTrajectory_TUM.txt"
    if not traj_file.exists():
        print(f"KeyFrameTrajectory_TUM.txt not found, checking CameraTrajectory_TUM.txt...")
        traj_file = result_dir / "CameraTrajectory_TUM.txt"

    kf_mapping = {} # index -> timestamp
    if traj_file.exists():
        print(f"Loading Keyframe mapping from {traj_file}")
        with open(traj_file, 'r') as f:
            idx = 0
            for line in f:
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    timestamp = int(float(parts[0]))
                    kf_mapping[idx] = timestamp
                    idx += 1
        print(f"Loaded {len(kf_mapping)} keyframes from trajectory file.")
    else:
        print(f"Warning: {traj_file} not found! Assuming Index=Timestamp (Likely wrong).")

    # Find unique frame IDs from files like "2881_10_depth.png"
    # Pattern: {iteration}_{fid}_depth.png
    pattern = re.compile(r'\d+_(\d+)_depth\.png$')
    
    frame_ids = []
    for f in depth_dir.glob('*_depth.png'):
        match = pattern.match(f.name)
        if match:
            frame_ids.append(int(match.group(1)))
    
    frame_ids = sorted(list(set(frame_ids)))
    print(f"Found {len(frame_ids)} keyframe files: {frame_ids}")

    # Process each frame
    script_path = Path(__file__).parent / "compare_single_frame_mesh.py"
    
    for i, fid in enumerate(frame_ids):
        # Determine GT Frame ID
        gt_fid = kf_mapping.get(fid, fid) # Default to fid if map missing
        
        print(f"[{i+1}/{len(frame_ids)}] Processing Keyframe {fid} -> GT Frame {gt_fid}...")
        
        cmd = [
            sys.executable, str(script_path),
            '--frame_id', str(fid),
            '--gt_frame_id', str(gt_fid),
            '--result_dir', str(result_dir),
            '--gt_depth_dir', args.gt_depth_dir,
            '--gt_traj', args.gt_traj,
            '--est_traj', str(traj_file),
            '--output_dir', f"{args.output_dir}/frame{fid}"
        ]
        
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error processing frame {fid}: {e}")

if __name__ == '__main__':
    main()
