#!/usr/bin/env python3
"""
Generate mesh from TUM RGB-D dataset using TSDF fusion with Open3D.

Usage:
    python tsdf_mesh_from_tum.py --dataset_path /path/to/tum/freiburg1_desk \
                                  --output_mesh output.ply \
                                  --voxel_size 0.01
"""

import open3d as o3d
import numpy as np
import argparse
from pathlib import Path
import sys


def read_tum_trajectory(trajectory_file):
    """
    Read TUM trajectory file (groundtruth.txt or estimated poses).
    
    Format: timestamp tx ty tz qx qy qz qw
    Returns: dict mapping timestamp to 4x4 pose matrix
    """
    poses = {}
    with open(trajectory_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            
            timestamp = float(parts[0])
            tx, ty, tz = map(float, parts[1:4])
            qx, qy, qz, qw = map(float, parts[4:8])
            
            # Convert quaternion to rotation matrix
            pose = np.eye(4)
            
            # Quaternion to rotation matrix
            # Normalize quaternion
            q_norm = np.sqrt(qx**2 + qy**2 + qz**2 + qw**2)
            qx, qy, qz, qw = qx/q_norm, qy/q_norm, qz/q_norm, qw/q_norm
            
            # Rotation matrix from quaternion
            pose[0, 0] = 1 - 2*qy**2 - 2*qz**2
            pose[0, 1] = 2*qx*qy - 2*qz*qw
            pose[0, 2] = 2*qx*qz + 2*qy*qw
            pose[1, 0] = 2*qx*qy + 2*qz*qw
            pose[1, 1] = 1 - 2*qx**2 - 2*qz**2
            pose[1, 2] = 2*qy*qz - 2*qx*qw
            pose[2, 0] = 2*qx*qz - 2*qy*qw
            pose[2, 1] = 2*qy*qz + 2*qx*qw
            pose[2, 2] = 1 - 2*qx**2 - 2*qy**2
            
            # Translation
            pose[0, 3] = tx
            pose[1, 3] = ty
            pose[2, 3] = tz
            
            poses[timestamp] = pose
    
    return poses


def read_tum_associations(association_file):
    """
    Read TUM associations.txt file.
    
    Format: timestamp_rgb rgb_file timestamp_depth depth_file
    Returns: list of (rgb_timestamp, rgb_file, depth_timestamp, depth_file)
    """
    associations = []
    with open(association_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            
            rgb_timestamp = float(parts[0])
            rgb_file = parts[1]
            depth_timestamp = float(parts[2])
            depth_file = parts[3]
            
            associations.append((rgb_timestamp, rgb_file, depth_timestamp, depth_file))
    
    return associations


def get_tum_intrinsics(dataset_name):
    """
    Get camera intrinsics for TUM RGB-D datasets.
    
    Returns: Open3D PinholeCameraIntrinsic object
    """
    # TUM RGB-D intrinsics (standard for Freiburg datasets)
    width = 640
    height = 480
    
    if 'freiburg1' in dataset_name.lower():
        fx, fy = 517.3, 516.5
        cx, cy = 318.6, 255.3
    elif 'freiburg2' in dataset_name.lower():
        fx, fy = 520.9, 521.0
        cx, cy = 325.1, 249.7
    elif 'freiburg3' in dataset_name.lower():
        fx, fy = 535.4, 539.2
        cx, cy = 320.1, 247.6
    else:
        # Default values (Freiburg1)
        print(f"Warning: Unknown dataset {dataset_name}, using default Freiburg1 intrinsics")
        fx, fy = 517.3, 516.5
        cx, cy = 318.6, 255.3
    
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        width=width,
        height=height,
        fx=fx,
        fy=fy,
        cx=cx,
        cy=cy
    )
    
    return intrinsic


def find_closest_pose(timestamp, poses):
    """Find the pose with closest timestamp."""
    timestamps = np.array(list(poses.keys()))
    idx = np.argmin(np.abs(timestamps - timestamp))
    closest_timestamp = timestamps[idx]
    
    # Check if timestamp difference is reasonable (< 0.02 seconds)
    if abs(closest_timestamp - timestamp) > 0.02:
        return None
    
    return poses[closest_timestamp]


def create_mesh_from_tum(dataset_path, output_mesh, trajectory_file=None,
                         voxel_size=0.01, sdf_trunc=0.04, depth_scale=5000.0,
                         depth_trunc=3.0, max_frames=None, stride=1):
    """
    Create mesh from TUM RGB-D dataset using TSDF fusion.
    
    Args:
        dataset_path: Path to TUM dataset directory
        output_mesh: Output mesh file path (.ply)
        trajectory_file: Path to trajectory file (default: groundtruth.txt in dataset)
        voxel_size: TSDF voxel size in meters (default: 0.01 = 1cm)
        sdf_trunc: TSDF truncation distance (default: 0.04 = 4cm)
        depth_scale: Depth image scale factor (TUM: 5000.0)
        depth_trunc: Maximum depth in meters (default: 3.0m)
        max_frames: Maximum number of frames to process (None = all)
        stride: Frame stride (1 = every frame, 2 = every other frame, etc.)
    """
    dataset_path = Path(dataset_path)
    
    # Read trajectory
    if trajectory_file is None:
        trajectory_file = dataset_path / "groundtruth.txt"
    
    if not trajectory_file.exists():
        print(f"Error: Trajectory file not found: {trajectory_file}")
        sys.exit(1)
    
    print(f"Reading trajectory from: {trajectory_file}")
    poses = read_tum_trajectory(trajectory_file)
    print(f"Loaded {len(poses)} poses")
    
    # Read associations
    association_file = dataset_path / "associations.txt"
    if not association_file.exists():
        print(f"Error: associations.txt not found in {dataset_path}")
        print("Please generate associations.txt using TUM tools:")
        print("  python associate.py rgb.txt depth.txt > associations.txt")
        sys.exit(1)
    
    print(f"Reading associations from: {association_file}")
    associations = read_tum_associations(association_file)
    print(f"Loaded {len(associations)} RGB-D pairs")
    
    # Get intrinsics
    dataset_name = dataset_path.name
    intrinsic = get_tum_intrinsics(dataset_name)
    print(f"Camera intrinsics: fx={intrinsic.intrinsic_matrix[0,0]:.1f}, "
          f"fy={intrinsic.intrinsic_matrix[1,1]:.1f}, "
          f"cx={intrinsic.intrinsic_matrix[0,2]:.1f}, "
          f"cy={intrinsic.intrinsic_matrix[1,2]:.1f}")
    
    # Create TSDF volume
    print(f"\nInitializing TSDF volume:")
    print(f"  Voxel size: {voxel_size}m")
    print(f"  SDF truncation: {sdf_trunc}m")
    
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    # Integrate frames
    num_frames = len(associations)
    if max_frames is not None:
        num_frames = min(num_frames, max_frames)
    
    print(f"\nIntegrating {num_frames} frames (stride={stride})...")
    integrated_count = 0
    
    for i in range(0, num_frames, stride):
        rgb_timestamp, rgb_file, depth_timestamp, depth_file = associations[i]
        
        # Find closest pose
        pose = find_closest_pose(depth_timestamp, poses)
        if pose is None:
            print(f"  Frame {i}: No matching pose found (skipping)")
            continue
        
        # Read images
        rgb_path = dataset_path / rgb_file
        depth_path = dataset_path / depth_file
        
        if not rgb_path.exists() or not depth_path.exists():
            print(f"  Frame {i}: Image files not found (skipping)")
            continue
        
        color = o3d.io.read_image(str(rgb_path))
        depth = o3d.io.read_image(str(depth_path))
        
        # Create RGBD image
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color, depth,
            depth_scale=depth_scale,
            depth_trunc=depth_trunc,
            convert_rgb_to_intensity=False
        )
        
        # Integrate into TSDF
        volume.integrate(
            rgbd,
            intrinsic,
            np.linalg.inv(pose)  # Open3D uses camera-to-world, we have world-to-camera
        )
        
        integrated_count += 1
        
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{num_frames} frames ({integrated_count} integrated)")
    
    print(f"\nTotal integrated frames: {integrated_count}")
    
    # Extract mesh
    print("\nExtracting triangle mesh...")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    print(f"Mesh vertices: {len(mesh.vertices)}")
    print(f"Mesh triangles: {len(mesh.triangles)}")
    
    # Save mesh
    output_mesh = Path(output_mesh)
    output_mesh.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\nSaving mesh to: {output_mesh}")
    o3d.io.write_triangle_mesh(str(output_mesh), mesh)
    
    print("Done!")
    
    return mesh


def main():
    parser = argparse.ArgumentParser(
        description='Generate mesh from TUM RGB-D dataset using TSDF fusion'
    )
    parser.add_argument(
        '--dataset_path',
        type=str,
        required=True,
        help='Path to TUM dataset directory (e.g., /data/TUM/freiburg1_desk)'
    )
    parser.add_argument(
        '--output_mesh',
        type=str,
        required=True,
        help='Output mesh file path (.ply)'
    )
    parser.add_argument(
        '--trajectory_file',
        type=str,
        default=None,
        help='Path to trajectory file (default: groundtruth.txt in dataset)'
    )
    parser.add_argument(
        '--voxel_size',
        type=float,
        default=0.01,
        help='TSDF voxel size in meters (default: 0.01 = 1cm)'
    )
    parser.add_argument(
        '--sdf_trunc',
        type=float,
        default=0.04,
        help='TSDF truncation distance in meters (default: 0.04 = 4cm)'
    )
    parser.add_argument(
        '--depth_scale',
        type=float,
        default=5000.0,
        help='Depth scale factor (TUM default: 5000.0)'
    )
    parser.add_argument(
        '--depth_trunc',
        type=float,
        default=3.0,
        help='Maximum depth in meters (default: 3.0)'
    )
    parser.add_argument(
        '--max_frames',
        type=int,
        default=None,
        help='Maximum number of frames to process (default: all)'
    )
    parser.add_argument(
        '--stride',
        type=int,
        default=1,
        help='Frame stride (1=every frame, 2=every other frame, etc.)'
    )
    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Visualize the generated mesh after creation'
    )
    
    args = parser.parse_args()
    
    # Create mesh
    mesh = create_mesh_from_tum(
        dataset_path=args.dataset_path,
        output_mesh=args.output_mesh,
        trajectory_file=args.trajectory_file,
        voxel_size=args.voxel_size,
        sdf_trunc=args.sdf_trunc,
        depth_scale=args.depth_scale,
        depth_trunc=args.depth_trunc,
        max_frames=args.max_frames,
        stride=args.stride
    )
    
    # Visualize if requested
    if args.visualize:
        print("\nVisualizing mesh...")
        o3d.visualization.draw_geometries([mesh])


if __name__ == '__main__':
    main()
