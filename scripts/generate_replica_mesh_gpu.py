#!/usr/bin/env python3
"""
GPU-accelerated TSDF mesh generation for Photo-SLAM Replica results.

Uses Open3D Tensor API with CUDA for ~10x faster mesh generation.

Usage:
    python3 generate_replica_mesh_gpu.py \
        --result_dir /path/to/results/replica_rgbd_0/office0 \
        --dataset_path /path/to/Replica/office0 \
        --output /path/to/output.ply
"""

import open3d as o3d
import open3d.core as o3c
import numpy as np
import argparse
from pathlib import Path
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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


def check_cuda():
    """Check if CUDA is available."""
    if o3c.cuda.is_available():
        logger.info(f"CUDA is available! Device count: {o3c.cuda.device_count()}")
        return o3c.Device("CUDA:0")
    else:
        logger.warning("CUDA not available, falling back to CPU")
        return o3c.Device("CPU:0")


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


def create_tsdf_mesh_gpu(
    result_dir: Path,
    dataset_path: Path,
    output_path: Path,
    voxel_size: float = 0.01,
    sdf_trunc: float = 0.04,
    depth_scale: float = 6553.5,
    depth_max: float = 10.0,
    stride: int = 1,
    use_rendered_depth: bool = True,
    intrinsics: dict = None
):
    """
    Create TSDF mesh using GPU-accelerated integration.
    
    Uses Open3D Tensor API with VoxelBlockGrid for CUDA acceleration.
    """
    
    if intrinsics is None:
        intrinsics = REPLICA_INTRINSICS
    
    # Check CUDA availability
    device = check_cuda()
    logger.info(f"Using device: {device}")
    
    # Read trajectory
    trajectory_file = result_dir / "CameraTrajectory_TUM.txt"
    if not trajectory_file.exists():
        raise FileNotFoundError(f"Trajectory file not found: {trajectory_file}")
    
    poses = read_tum_trajectory(trajectory_file)
    
    # Find frames
    frames = find_replica_frames(dataset_path)
    
    # Create Tensor intrinsic matrix
    intrinsic_t = o3c.Tensor([
        [intrinsics['fx'], 0, intrinsics['cx']],
        [0, intrinsics['fy'], intrinsics['cy']],
        [0, 0, 1]
    ], dtype=o3c.float64, device=device)
    
    # Create VoxelBlockGrid for GPU TSDF
    # Block resolution determines memory/accuracy trade-off
    block_resolution = 8  # 8x8x8 voxels per block
    block_count = 100000  # Initial hash table size
    
    vbg = o3d.t.geometry.VoxelBlockGrid(
        attr_names=('tsdf', 'weight', 'color'),
        attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
        attr_channels=((1,), (1,), (3,)),
        voxel_size=voxel_size,
        block_resolution=block_resolution,
        block_count=block_count,
        device=device
    )
    
    logger.info(f"Created VoxelBlockGrid on {device}")
    logger.info(f"  Voxel size: {voxel_size}m")
    logger.info(f"  SDF truncation: {sdf_trunc}m")
    logger.info(f"  Block resolution: {block_resolution}")
    
    # Integrate frames
    logger.info("Integrating frames into TSDF volume (GPU)...")
    start_time = time.time()
    
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
        
        try:
            # Read images as tensors
            color_legacy = o3d.io.read_image(str(rgb_path))
            depth_legacy = o3d.io.read_image(str(depth_path))
            
            # Convert to tensor images
            color_t = o3d.t.geometry.Image.from_legacy(color_legacy, device=device)
            depth_t = o3d.t.geometry.Image.from_legacy(depth_legacy, device=device)
            
            # Create extrinsic (world-to-camera) from pose (camera-to-world)
            extrinsic = np.linalg.inv(pose)
            extrinsic_t = o3c.Tensor(extrinsic, dtype=o3c.float64, device=device)
            
            # Compute frustum block coordinates first (required for VoxelBlockGrid API)
            frustum_block_coords = vbg.compute_unique_block_coordinates(
                depth_t, intrinsic_t, extrinsic_t,
                depth_scale=depth_scale,
                depth_max=depth_max
            )
            
            # Integrate with block_coords as first argument
            vbg.integrate(
                frustum_block_coords,
                depth_t, color_t,
                intrinsic_t, extrinsic_t,
                depth_scale=depth_scale,
                depth_max=depth_max
            )
            
            integrated_count += 1
            
            if integrated_count % 100 == 0:
                elapsed = time.time() - start_time
                fps = integrated_count / elapsed
                logger.info(f"  Integrated {integrated_count} frames ({fps:.1f} FPS)")
                
        except Exception as e:
            logger.warning(f"Failed to integrate frame {frame_id}: {e}")
            continue
    
    elapsed = time.time() - start_time
    fps = integrated_count / elapsed if elapsed > 0 else 0
    
    logger.info(f"Integration complete!")
    logger.info(f"  Frames integrated: {integrated_count}")
    logger.info(f"  Time: {elapsed:.1f}s")
    logger.info(f"  Average FPS: {fps:.1f}")
    
    # Extract mesh
    logger.info("Extracting mesh from TSDF volume...")
    mesh = vbg.extract_triangle_mesh()
    
    # Compute normals
    mesh.compute_vertex_normals()
    
    # Convert to legacy format for saving
    mesh_legacy = mesh.to_legacy()
    
    # Save mesh
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh_legacy)
    
    logger.info(f"Mesh saved to: {output_path}")
    logger.info(f"  Vertices: {len(mesh_legacy.vertices)}")
    logger.info(f"  Triangles: {len(mesh_legacy.triangles)}")
    
    return mesh_legacy


def create_tsdf_mesh_cpu(
    result_dir: Path,
    dataset_path: Path,
    output_path: Path,
    voxel_size: float = 0.01,
    sdf_trunc: float = 0.04,
    depth_scale: float = 6553.5,
    depth_trunc: float = 10.0,
    stride: int = 1,
    intrinsics: dict = None
):
    """
    Fallback CPU-based TSDF integration using legacy API.
    """
    
    if intrinsics is None:
        intrinsics = REPLICA_INTRINSICS
    
    logger.info("Using CPU-based TSDF integration (legacy API)")
    
    # Read trajectory
    trajectory_file = result_dir / "CameraTrajectory_TUM.txt"
    if not trajectory_file.exists():
        raise FileNotFoundError(f"Trajectory file not found: {trajectory_file}")
    
    poses = read_tum_trajectory(trajectory_file)
    frames = find_replica_frames(dataset_path)
    
    # Create legacy intrinsic
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        width=intrinsics['width'],
        height=intrinsics['height'],
        fx=intrinsics['fx'],
        fy=intrinsics['fy'],
        cx=intrinsics['cx'],
        cy=intrinsics['cy']
    )
    
    # Create TSDF volume
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    # Integrate
    logger.info("Integrating frames (CPU)...")
    start_time = time.time()
    integrated_count = 0
    pose_idx = 0
    
    for i, (frame_id, rgb_path, depth_path) in enumerate(frames):
        if i % stride != 0:
            continue
        
        if pose_idx >= len(poses):
            break
        
        timestamp, pose = poses[pose_idx]
        pose_idx += 1
        
        try:
            color = o3d.io.read_image(str(rgb_path))
            depth = o3d.io.read_image(str(depth_path))
            
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth,
                depth_scale=depth_scale,
                depth_trunc=depth_trunc,
                convert_rgb_to_intensity=False
            )
            
            volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))
            integrated_count += 1
            
            if integrated_count % 100 == 0:
                logger.info(f"  Integrated {integrated_count} frames")
                
        except Exception as e:
            continue
    
    elapsed = time.time() - start_time
    logger.info(f"Integration complete: {integrated_count} frames in {elapsed:.1f}s")
    
    # Extract mesh
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    
    logger.info(f"Mesh saved: {output_path}")
    return mesh


def main():
    parser = argparse.ArgumentParser(description='GPU-accelerated TSDF mesh generation')
    
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
    parser.add_argument('--depth_max', type=float, default=10.0,
                        help='Maximum depth (default: 10.0)')
    parser.add_argument('--stride', type=int, default=1,
                        help='Frame stride (default: 1)')
    parser.add_argument('--cpu', action='store_true',
                        help='Force CPU mode (disable GPU)')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    result_dir = Path(args.result_dir)
    dataset_path = Path(args.dataset_path)
    output_path = Path(args.output)
    
    if args.cpu or not o3c.cuda.is_available():
        create_tsdf_mesh_cpu(
            result_dir=result_dir,
            dataset_path=dataset_path,
            output_path=output_path,
            voxel_size=args.voxel_size,
            sdf_trunc=args.sdf_trunc,
            depth_scale=args.depth_scale,
            depth_trunc=args.depth_max,
            stride=args.stride
        )
    else:
        create_tsdf_mesh_gpu(
            result_dir=result_dir,
            dataset_path=dataset_path,
            output_path=output_path,
            voxel_size=args.voxel_size,
            sdf_trunc=args.sdf_trunc,
            depth_scale=args.depth_scale,
            depth_max=args.depth_max,
            stride=args.stride
        )


if __name__ == '__main__':
    main()
