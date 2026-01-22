#!/usr/bin/env python3
"""
Generate TSDF mesh from Photo-SLAM result for Replica dataset.

This script creates TSDF mesh using:
- Estimated camera trajectory from CameraTrajectory_TUM.txt
- Rendered depth images from Photo-SLAM
- RGB images from Replica dataset

Usage:
    python3 generate_replica_mesh.py \
        --result_dir /path/to/results/replica_rgbd_0/office0 \
        --dataset_path /path/to/Replica/office0 \
        --output /path/to/output.ply
"""

import open3d as o3d
import numpy as np
import argparse
from pathlib import Path
import cv2
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replica camera intrinsics (default)
REPLICA_INTRINSICS = {
    'width': 1200,
    'height': 680,
    'fx': 600.0,
    'fy': 600.0,
    'cx': 599.5,
    'cy': 339.5
}


def read_tum_trajectory(trajectory_file: Path):
    """
    Read TUM trajectory file (CameraTrajectory_TUM.txt).
    
    Format: timestamp tx ty tz qx qy qz qw
    Returns: list of (timestamp, 4x4 pose matrix)
    """
    poses = []
    
    with open(trajectory_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) < 8:
                continue
            
            timestamp = float(parts[0])
            tx, ty, tz = float(parts[1]), float(parts[2]), float(parts[3])
            qx, qy, qz, qw = float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])
            
            # Create rotation matrix from quaternion
            R = o3d.geometry.get_rotation_matrix_from_quaternion([qw, qx, qy, qz])
            
            # Create 4x4 pose matrix
            pose = np.eye(4)
            pose[:3, :3] = R
            pose[:3, 3] = [tx, ty, tz]
            
            poses.append((timestamp, pose))
    
    logger.info(f"Read {len(poses)} poses from trajectory")
    return poses


def find_replica_frames(dataset_path: Path):
    """
    Find all RGB and depth frames in Replica dataset.
    
    Returns: list of (frame_id, rgb_path, depth_path)
    """
    results_dir = dataset_path / "results"
    
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    
    frames = []
    
    # Find all depth frames
    depth_files = sorted(results_dir.glob("depth*.png"))
    
    for depth_file in depth_files:
        # Extract frame number from filename (e.g., depth000123.png -> 123)
        frame_id_str = depth_file.stem.replace("depth", "")
        try:
            frame_id = int(frame_id_str)
        except ValueError:
            continue
        
        # Find corresponding RGB
        rgb_file = results_dir / f"frame{frame_id_str}.jpg"
        if not rgb_file.exists():
            rgb_file = results_dir / f"frame{frame_id_str}.png"
        
        if rgb_file.exists():
            frames.append((frame_id, rgb_file, depth_file))
    
    logger.info(f"Found {len(frames)} frames in dataset")
    return frames


def find_rendered_depths(result_dir: Path):
    """
    Find rendered depth images from Photo-SLAM result.
    
    Returns: dict mapping frame_id to rendered depth path
    """
    rendered_depths = {}
    
    # Check for rendered depth images in result directory
    for depth_file in result_dir.glob("rendered_depth_*.png"):
        try:
            frame_id = int(depth_file.stem.replace("rendered_depth_", ""))
            rendered_depths[frame_id] = depth_file
        except ValueError:
            continue
    
    # Also check for depth_*.png pattern
    if not rendered_depths:
        for depth_file in result_dir.glob("depth_*.png"):
            try:
                frame_id = int(depth_file.stem.replace("depth_", ""))
                rendered_depths[frame_id] = depth_file
            except ValueError:
                continue
    
    logger.info(f"Found {len(rendered_depths)} rendered depth images")
    return rendered_depths


def get_intrinsic(width, height, fx, fy, cx, cy):
    """Create Open3D camera intrinsic object."""
    return o3d.camera.PinholeCameraIntrinsic(
        width=width, height=height,
        fx=fx, fy=fy, cx=cx, cy=cy
    )


def create_tsdf_mesh(
    result_dir: Path,
    dataset_path: Path,
    output_path: Path,
    voxel_size: float = 0.01,
    sdf_trunc: float = 0.04,
    depth_scale: float = 6553.5,
    depth_trunc: float = 10.0,
    stride: int = 1,
    use_rendered_depth: bool = True,
    intrinsics: dict = None
):
    """
    Create TSDF mesh from Photo-SLAM result.
    
    Args:
        result_dir: Path to Photo-SLAM result directory
        dataset_path: Path to Replica dataset
        output_path: Path to save output mesh
        voxel_size: TSDF voxel size in meters
        sdf_trunc: TSDF truncation distance
        depth_scale: Depth image scale factor
        depth_trunc: Maximum depth to use
        stride: Use every N-th frame
        use_rendered_depth: Use rendered depth instead of GT depth
        intrinsics: Camera intrinsics dict (optional)
    """
    
    if intrinsics is None:
        intrinsics = REPLICA_INTRINSICS
    
    # Read trajectory
    trajectory_file = result_dir / "CameraTrajectory_TUM.txt"
    if not trajectory_file.exists():
        raise FileNotFoundError(f"Trajectory file not found: {trajectory_file}")
    
    poses = read_tum_trajectory(trajectory_file)
    
    # Find frames
    frames = find_replica_frames(dataset_path)
    
    # Find rendered depths if using rendered depth
    rendered_depths = {}
    if use_rendered_depth:
        rendered_depths = find_rendered_depths(result_dir)
    
    # Create TSDF volume
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    # Camera intrinsic
    intrinsic = get_intrinsic(
        intrinsics['width'], intrinsics['height'],
        intrinsics['fx'], intrinsics['fy'],
        intrinsics['cx'], intrinsics['cy']
    )
    
    # Integrate frames
    logger.info("Integrating frames into TSDF volume...")
    
    integrated_count = 0
    pose_idx = 0
    
    for i, (frame_id, rgb_path, depth_path) in enumerate(frames):
        if i % stride != 0:
            continue
        
        # Find closest pose
        if pose_idx >= len(poses):
            break
        
        timestamp, pose = poses[pose_idx]
        pose_idx += 1
        
        # Get depth image
        if use_rendered_depth and frame_id in rendered_depths:
            depth_img_path = rendered_depths[frame_id]
        else:
            depth_img_path = depth_path
        
        # Read images
        try:
            color = o3d.io.read_image(str(rgb_path))
            depth = o3d.io.read_image(str(depth_img_path))
        except Exception as e:
            logger.warning(f"Failed to read frame {frame_id}: {e}")
            continue
        
        # Create RGBD image
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color, depth,
            depth_scale=depth_scale,
            depth_trunc=depth_trunc,
            convert_rgb_to_intensity=False
        )
        
        # Integrate
        volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))
        integrated_count += 1
        
        if integrated_count % 100 == 0:
            logger.info(f"  Integrated {integrated_count} frames")
    
    logger.info(f"Total integrated frames: {integrated_count}")
    
    # Extract mesh
    logger.info("Extracting mesh from TSDF volume...")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    # Save mesh
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    
    logger.info(f"Mesh saved to: {output_path}")
    logger.info(f"  Vertices: {len(mesh.vertices)}")
    logger.info(f"  Triangles: {len(mesh.triangles)}")
    
    return mesh


def main():
    parser = argparse.ArgumentParser(description='Generate TSDF mesh from Photo-SLAM Replica result')
    
    parser.add_argument('--result_dir', type=str, required=True,
                        help='Path to Photo-SLAM result directory')
    parser.add_argument('--dataset_path', type=str, required=True,
                        help='Path to Replica dataset')
    parser.add_argument('--output', type=str, required=True,
                        help='Output mesh path')
    parser.add_argument('--voxel_size', type=float, default=0.01,
                        help='TSDF voxel size (default: 0.01)')
    parser.add_argument('--sdf_trunc', type=float, default=0.04,
                        help='SDF truncation distance (default: 0.04)')
    parser.add_argument('--depth_scale', type=float, default=6553.5,
                        help='Depth scale factor (default: 6553.5 for Replica)')
    parser.add_argument('--depth_trunc', type=float, default=10.0,
                        help='Maximum depth (default: 10.0)')
    parser.add_argument('--stride', type=int, default=1,
                        help='Frame stride (default: 1)')
    parser.add_argument('--use_gt_depth', action='store_true',
                        help='Use GT depth instead of rendered depth')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    result_dir = Path(args.result_dir)
    dataset_path = Path(args.dataset_path)
    output_path = Path(args.output)
    
    create_tsdf_mesh(
        result_dir=result_dir,
        dataset_path=dataset_path,
        output_path=output_path,
        voxel_size=args.voxel_size,
        sdf_trunc=args.sdf_trunc,
        depth_scale=args.depth_scale,
        depth_trunc=args.depth_trunc,
        stride=args.stride,
        use_rendered_depth=not args.use_gt_depth
    )


if __name__ == '__main__':
    main()
