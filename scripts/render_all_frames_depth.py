#!/usr/bin/env python3
"""
Render depth for ALL frames using trained Photo-SLAM Gaussians.
This supplements the keyframe-only depth saved by Photo-SLAM.
"""

import torch
import numpy as np
import argparse
from pathlib import Path
import logging
from PIL import Image
from plyfile import PlyData
import cv2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()

# Try to import diff_gaussian_rasterization
try:
    from diff_gaussian_rasterization import GaussianRasterizationSettings, GaussianRasterizer
    HAS_RASTERIZER = True
except ImportError:
    HAS_RASTERIZER = False
    logger.warning("diff_gaussian_rasterization not available. Using simple projection instead.")


def read_replica_trajectory(traj_file: Path):
    """Read Replica trajectory (4x4 matrices)."""
    poses = {}
    with open(traj_file, 'r') as f:
        for i, line in enumerate(f):
            values = [float(x) for x in line.strip().split()]
            if len(values) == 16:
                poses[i] = np.array(values).reshape(4, 4)
    return poses


def load_gaussians(ply_path: Path):
    """Load Gaussian parameters from PLY file."""
    plydata = PlyData.read(str(ply_path))
    
    xyz = np.stack([
        plydata['vertex']['x'],
        plydata['vertex']['y'],
        plydata['vertex']['z']
    ], axis=1).astype(np.float32)
    
    return xyz


def project_points_to_depth(xyz, pose, intrinsics, width, height):
    """Project 3D points to depth map using simple projection."""
    # Transform to camera coordinates
    R = pose[:3, :3]
    t = pose[:3, 3]
    
    # World to camera: p_cam = R.T @ (p_world - t)
    xyz_cam = (xyz - t) @ R
    
    # Filter points behind camera
    valid = xyz_cam[:, 2] > 0.1
    xyz_cam = xyz_cam[valid]
    
    if len(xyz_cam) == 0:
        return np.zeros((height, width), dtype=np.float32)
    
    # Project to image
    fx, fy, cx, cy = intrinsics['fx'], intrinsics['fy'], intrinsics['cx'], intrinsics['cy']
    u = (xyz_cam[:, 0] / xyz_cam[:, 2]) * fx + cx
    v = (xyz_cam[:, 1] / xyz_cam[:, 2]) * fy + cy
    z = xyz_cam[:, 2]
    
    # Filter points outside image
    valid = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    u, v, z = u[valid].astype(int), v[valid].astype(int), z[valid]
    
    # Create depth map (keep closest point for each pixel)
    depth = np.full((height, width), np.inf, dtype=np.float32)
    for ui, vi, zi in zip(u, v, z):
        if zi < depth[vi, ui]:
            depth[vi, ui] = zi
    
    depth[depth == np.inf] = 0
    return depth


def main():
    parser = argparse.ArgumentParser(description='Render depth for all frames')
    parser.add_argument('--result_dir', required=True, help='PA6 result directory')
    parser.add_argument('--dataset_path', required=True, help='Replica dataset path')
    parser.add_argument('--output_dir', required=True, help='Output depth directory')
    parser.add_argument('--depth_scale', type=float, default=6553.5, help='Depth scale for saving')
    parser.add_argument('--stride', type=int, default=1, help='Frame stride (1=all frames)')
    args = parser.parse_args()
    
    result_dir = Path(args.result_dir)
    dataset_path = Path(args.dataset_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find Gaussian PLY
    ply_files = list(result_dir.glob('*_shutdown/ply/*.ply'))
    if not ply_files:
        raise FileNotFoundError(f"No PLY found in {result_dir}")
    
    ply_path = ply_files[0]
    logger.info(f'Loading Gaussians: {ply_path}')
    xyz = load_gaussians(ply_path)
    logger.info(f'Loaded {len(xyz)} Gaussian centers')
    
    # Load GT trajectory
    gt_poses = read_replica_trajectory(dataset_path / 'traj.txt')
    logger.info(f'Loaded {len(gt_poses)} GT poses')
    
    # Intrinsics (Replica)
    intrinsics = {'fx': 600.0, 'fy': 600.0, 'cx': 599.5, 'cy': 339.5}
    width, height = 1200, 680
    
    # Render depth for all frames
    logger.info(f'Rendering depth for {len(gt_poses)//args.stride} frames (stride={args.stride})...')
    
    for fid in range(0, len(gt_poses), args.stride):
        if fid not in gt_poses:
            continue
        
        pose = gt_poses[fid]
        depth = project_points_to_depth(xyz, pose, intrinsics, width, height)
        
        # Save as 16-bit PNG
        depth_16u = (depth * args.depth_scale).astype(np.uint16)
        cv2.imwrite(str(output_dir / f'depth_{fid:06d}.png'), depth_16u)
        
        if fid % 100 == 0:
            logger.info(f'  Frame {fid}/{len(gt_poses)}')
    
    logger.info(f'Saved depth maps to {output_dir}')


if __name__ == '__main__':
    main()
