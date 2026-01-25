#!/usr/bin/env python3
"""
Generate mesh from Photo-SLAM PA6 v2 rendered depth + poses.
Uses corrected depth scale (6553.5 for Replica).
"""

import numpy as np
import open3d as o3d
import argparse
from pathlib import Path
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

REPLICA_INTRINSICS = {
    'width': 1200,
    'height': 680,
    'fx': 600.0,
    'fy': 600.0,
    'cx': 599.5,
    'cy': 339.5
}


def read_tum_trajectory(traj_file: Path):
    """Read TUM format trajectory."""
    poses = {}
    with open(traj_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            
            timestamp = float(parts[0])
            frame_id = int(timestamp)
            tx, ty, tz = float(parts[1]), float(parts[2]), float(parts[3])
            qx, qy, qz, qw = float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])
            
            R = o3d.geometry.get_rotation_matrix_from_quaternion([qw, qx, qy, qz])
            pose = np.eye(4)
            pose[:3, :3] = R
            pose[:3, 3] = [tx, ty, tz]
            poses[frame_id] = pose
    return poses


def find_photoslam_depth(result_dir: Path):
    """Find Photo-SLAM rendered depth files."""
    depth_files = {}
    for shutdown_dir in result_dir.glob("*_shutdown"):
        depth_dir = shutdown_dir / "depth"
        if not depth_dir.exists():
            continue
        for depth_file in depth_dir.glob("*_depth.png"):
            match = re.search(r'_(\d+)_depth\.png$', depth_file.name)
            if match:
                frame_id = int(match.group(1))
                depth_files[frame_id] = depth_file
    logger.info(f"Found {len(depth_files)} Photo-SLAM depth files")
    return depth_files


def create_mesh(
    result_dir: Path,
    output_path: Path,
    voxel_size: float = 0.02,
    sdf_trunc: float = 0.06,
    depth_scale: float = 6553.5  # Correct scale for Replica
):
    """Create mesh from Photo-SLAM rendered depth + poses."""
    
    # Load trajectory
    traj_file = result_dir / "CameraTrajectory_TUM.txt"
    estimated_poses = read_tum_trajectory(traj_file)
    logger.info(f"Loaded {len(estimated_poses)} poses")
    
    # Find Photo-SLAM depth files
    depth_files = find_photoslam_depth(result_dir)
    
    # Create intrinsics
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        REPLICA_INTRINSICS['width'], REPLICA_INTRINSICS['height'],
        REPLICA_INTRINSICS['fx'], REPLICA_INTRINSICS['fy'],
        REPLICA_INTRINSICS['cx'], REPLICA_INTRINSICS['cy']
    )
    
    # TSDF Volume
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    logger.info(f"Integrating depth maps (voxel={voxel_size}m, scale={depth_scale})...")
    integrated = 0
    
    for frame_id, depth_path in sorted(depth_files.items()):
        if frame_id not in estimated_poses:
            continue
        
        try:
            # Read depth
            depth = o3d.io.read_image(str(depth_path))
            
            # Dummy color
            color_np = np.ones((REPLICA_INTRINSICS['height'], 
                                REPLICA_INTRINSICS['width'], 3), dtype=np.uint8) * 128
            color = o3d.geometry.Image(color_np)
            
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth,
                depth_scale=depth_scale,
                depth_trunc=10.0,
                convert_rgb_to_intensity=False
            )
            
            pose = estimated_poses[frame_id]
            volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))
            integrated += 1
            
            if integrated % 20 == 0:
                logger.info(f"  Integrated {integrated}/{len(depth_files)} frames")
            
        except Exception as e:
            logger.warning(f"Failed frame {frame_id}: {e}")
    
    logger.info(f"Integration complete: {integrated} frames")
    
    # Extract mesh
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    logger.info(f"Saved mesh to {output_path} ({len(mesh.vertices)} vertices)")


def main():
    parser = argparse.ArgumentParser(description="Generate mesh from Photo-SLAM PA6 v2 depth")
    parser.add_argument('--result_dir', required=True, help='Path to PA6 results')
    parser.add_argument('--output', required=True, help='Output mesh path')
    parser.add_argument('--voxel_size', type=float, default=0.02, help='Voxel size')
    parser.add_argument('--depth_scale', type=float, default=6553.5, help='Depth scale (6553.5 for Replica)')
    args = parser.parse_args()
    
    create_mesh(Path(args.result_dir), Path(args.output),
                args.voxel_size, depth_scale=args.depth_scale)


if __name__ == '__main__':
    main()
