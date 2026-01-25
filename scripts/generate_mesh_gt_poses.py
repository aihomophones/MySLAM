#!/usr/bin/env python3
"""
Generate TSDF mesh using Replica GT poses instead of Photo-SLAM estimated poses.
This helps verify if the issue is with poses or depth maps.
"""

import open3d as o3d
import numpy as np
import argparse
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Replica camera intrinsics
REPLICA_INTRINSICS = {
    'width': 1200,
    'height': 680,
    'fx': 600.0,
    'fy': 600.0,
    'cx': 599.5,
    'cy': 339.5
}


def load_replica_poses(traj_file: Path):
    """Load all poses from Replica traj.txt (4x4 matrix per line)."""
    poses = []
    with open(traj_file, 'r') as f:
        for line in f:
            values = [float(x) for x in line.strip().split()]
            if len(values) == 16:
                pose = np.array(values).reshape(4, 4)
                poses.append(pose)
    logger.info(f"Loaded {len(poses)} GT poses from {traj_file}")
    return poses


def find_frames(dataset_path: Path):
    """Find RGB and depth frames."""
    results_dir = dataset_path / "results"
    frames = []
    depth_files = sorted(results_dir.glob("depth*.png"))
    
    for depth_file in depth_files:
        frame_id_str = depth_file.stem.replace("depth", "")
        try:
            frame_id = int(frame_id_str)
        except ValueError:
            continue
        
        rgb_file = results_dir / f"frame{frame_id_str}.jpg"
        if not rgb_file.exists():
            rgb_file = results_dir / f"frame{frame_id_str}.png"
        
        if rgb_file.exists():
            frames.append((frame_id, rgb_file, depth_file))
    
    logger.info(f"Found {len(frames)} frames")
    return frames


def create_mesh_with_gt_poses(
    dataset_path: Path,
    output_path: Path,
    voxel_size: float = 0.01,
    sdf_trunc: float = 0.04,
    depth_scale: float = 6553.5,
    stride: int = 1
):
    """Create TSDF mesh using GT poses from Replica."""
    
    # Load GT poses
    traj_file = dataset_path / "traj.txt"
    poses = load_replica_poses(traj_file)
    
    # Find frames
    frames = find_frames(dataset_path)
    
    # Create intrinsics
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        width=REPLICA_INTRINSICS['width'],
        height=REPLICA_INTRINSICS['height'],
        fx=REPLICA_INTRINSICS['fx'],
        fy=REPLICA_INTRINSICS['fy'],
        cx=REPLICA_INTRINSICS['cx'],
        cy=REPLICA_INTRINSICS['cy']
    )
    
    # Create TSDF volume
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    logger.info("Integrating frames with GT poses...")
    integrated = 0
    
    for i, (frame_id, rgb_path, depth_path) in enumerate(frames):
        if i % stride != 0:
            continue
        
        if i >= len(poses):
            break
        
        try:
            color = o3d.io.read_image(str(rgb_path))
            depth = o3d.io.read_image(str(depth_path))
            
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth,
                depth_scale=depth_scale,
                depth_trunc=10.0,
                convert_rgb_to_intensity=False
            )
            
            # Use GT pose directly (Replica format is already camera-to-world)
            pose = poses[i]
            
            # NOTE: Testing WITHOUT coordinate conversion
            # pose_cv = pose.copy()
            # pose_cv[:3, 1] *= -1
            # pose_cv[:3, 2] *= -1
            
            volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))
            integrated += 1
            
            if integrated % 100 == 0:
                logger.info(f"  Integrated {integrated} frames")
                
        except Exception as e:
            logger.warning(f"Failed frame {frame_id}: {e}")
            continue
    
    logger.info(f"Integration complete: {integrated} frames")
    
    # Extract mesh
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    logger.info(f"Saved mesh to {output_path}")
    
    return mesh


def main():
    parser = argparse.ArgumentParser(description='Generate mesh using Replica GT poses')
    parser.add_argument('--dataset_path', type=str, required=True)
    parser.add_argument('--output', type=str, required=True)
    parser.add_argument('--voxel_size', type=float, default=0.01)
    parser.add_argument('--stride', type=int, default=1)
    
    args = parser.parse_args()
    
    create_mesh_with_gt_poses(
        Path(args.dataset_path),
        Path(args.output),
        voxel_size=args.voxel_size,
        stride=args.stride
    )


if __name__ == '__main__':
    main()
