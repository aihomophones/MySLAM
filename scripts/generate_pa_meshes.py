#!/usr/bin/env python3
"""
Generate TSDF meshes for all Photo-SLAM experiment variants (PA1-PA10).

This script creates dense 3D meshes from estimated camera trajectories
using TSDF volumetric fusion. Each PA variant's estimated poses are used
to create meshes that can be evaluated for geometric accuracy.

Usage:
    # Generate meshes for all PA variants
    python generate_pa_meshes.py --all
    
    # Generate meshes for specific PA variants
    python generate_pa_meshes.py --pa PA6 PA7
    
    # Use specific TUM data path
    python generate_pa_meshes.py --all --data_path /path/to/TUM
    
    # High quality meshes (slower, larger)
    python generate_pa_meshes.py --all --voxel_size 0.005
"""

import open3d as o3d
import numpy as np
import argparse
from pathlib import Path
import sys
from typing import Dict, List, Tuple
import logging
import json
import glob
import os

# Configure logging - moved to main
logger = logging.getLogger(__name__)


# TUM RGB-D datasets configuration
TUM_DATASETS = [
    'rgbd_dataset_freiburg1_desk',
    'rgbd_dataset_freiburg2_xyz',
    'rgbd_dataset_freiburg3_long_office_household'
]

# PA variants configuration
PA_VARIANTS = {
    'PA1': {'lambda_align': 0.05, 'lambda_geo': 0.0, 'description': 'L_align only'},
    'PA3': {'lambda_align': 0.05, 'lambda_geo': 0.0, 'description': 'L_align + L_iso'},
    'PA4': {'lambda_align': 0.05, 'lambda_geo': 0.0, 'description': 'L_align (iso disabled)'},
    'PA5': {'lambda_align': 0.0, 'lambda_geo': 1.0, 'description': 'L_sensor λ=1.0'},
    'PA6': {'lambda_align': 0.0, 'lambda_geo': 0.2, 'description': 'L_sensor λ=0.2 ⭐BEST'},
    'PA7': {'lambda_align': 0.0, 'lambda_geo': 0.25, 'description': 'L_sensor λ=0.25'},
    'PA8': {'lambda_align': 0.05, 'lambda_geo': 0.2, 'description': 'L_sensor + L_align'},
    'PA9': {'lambda_align': 0.0, 'lambda_geo': 0.15, 'description': 'L_sensor λ=0.15'},
    'PA10': {'lambda_align': 0.0, 'lambda_geo': 0.5, 'description': 'L_sensor λ=0.5'},
}


def read_tum_trajectory(trajectory_file: Path) -> Dict[float, np.ndarray]:
    """
    Read TUM trajectory file (CameraTrajectory_TUM.txt).
    
    Format: timestamp tx ty tz qx qy qz qw
    Returns: dict mapping timestamp to 4x4 pose matrix
    """
    poses = {}
    
    if not trajectory_file.exists():
        logger.error(f"Trajectory file not found: {trajectory_file}")
        return poses
    
    with open(trajectory_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            
            try:
                timestamp = float(parts[0])
                tx, ty, tz = map(float, parts[1:4])
                qx, qy, qz, qw = map(float, parts[4:8])
                
                # Convert quaternion to rotation matrix
                pose = np.eye(4)
                
                # Normalize quaternion
                q_norm = np.sqrt(qx**2 + qy**2 + qz**2 + qw**2)
                if q_norm < 1e-10:
                    continue
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
            except ValueError as e:
                logger.warning(f"Error parsing line: {line.strip()} - {e}")
                continue
    
    return poses


def read_tum_associations(association_file: Path) -> List[Tuple]:
    """
    Read TUM associations.txt file.
    
    Format: timestamp_rgb rgb_file timestamp_depth depth_file
    Returns: list of (rgb_timestamp, rgb_file, depth_timestamp, depth_file)
    """
    associations = []
    
    if not association_file.exists():
        logger.error(f"Association file not found: {association_file}")
        return associations
    
    with open(association_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            
            try:
                rgb_timestamp = float(parts[0])
                rgb_file = parts[1]
                depth_timestamp = float(parts[2])
                depth_file = parts[3]
                
                associations.append((rgb_timestamp, rgb_file, depth_timestamp, depth_file))
            except ValueError as e:
                logger.warning(f"Error parsing association: {line.strip()} - {e}")
                continue
    
    return associations


def get_tum_intrinsics(dataset_name: str) -> o3d.camera.PinholeCameraIntrinsic:
    """
    Get camera intrinsics for TUM RGB-D datasets.
    
    Returns: Open3D PinholeCameraIntrinsic object
    """
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
        logger.warning(f"Unknown dataset {dataset_name}, using default Freiburg1 intrinsics")
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


def find_closest_pose(timestamp: float, poses: Dict[float, np.ndarray], 
                      max_diff: float = 0.02) -> np.ndarray:
    """
    Find the pose with closest timestamp.
    
    Args:
        timestamp: Query timestamp
        poses: Dict of timestamp -> pose
        max_diff: Maximum acceptable time difference (seconds)
    
    Returns: 4x4 pose matrix or None if no close match
    """
    if not poses:
        return None
    
    timestamps = np.array(list(poses.keys()))
    idx = np.argmin(np.abs(timestamps - timestamp))
    closest_timestamp = timestamps[idx]
    
    # Check if timestamp difference is reasonable
    if abs(closest_timestamp - timestamp) > max_diff:
        return None
    
    return poses[closest_timestamp]


def create_mesh_from_pa_result(
    pa_name: str,
    dataset_name: str,
    tum_data_path: Path,
    pa_result_path: Path,
    output_mesh_path: Path,
    voxel_size: float = 0.01,
    sdf_trunc: float = 0.04,
    depth_scale: float = 5000.0,
    depth_trunc: float = 3.0,
    stride: int = 1,
    run_index: int = 0,
    use_rendered_depth: bool = False
) -> bool:

    """
    Create TSDF mesh from Photo-SLAM PA result.
    
    Args:
        pa_name: PA variant name (e.g., 'PA6')
        dataset_name: TUM dataset name
        tum_data_path: Path to TUM dataset (with RGB/depth images)
        pa_result_path: Path to PA result directory
        output_mesh_path: Output mesh file path
        voxel_size: TSDF voxel size in meters
        sdf_trunc: TSDF truncation distance
        depth_scale: Depth image scale factor (TUM: 5000.0)
        depth_trunc: Maximum depth in meters
        stride: Frame stride for integration
        run_index: Which run to use (0-9 for multiple runs)
    
    Returns: True if successful, False otherwise
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Creating mesh: {pa_name} - {dataset_name}")
    logger.info(f"{'='*60}")
    
    # Find trajectory file in PA result
    result_dir = pa_result_path / f"tum_rgbd_{run_index}" / dataset_name
    trajectory_file = result_dir / "CameraTrajectory_TUM.txt"
    
    if not trajectory_file.exists():
        logger.error(f"Trajectory file not found: {trajectory_file}")
        return False
    
    # Read estimated trajectory
    logger.info(f"Reading trajectory from: {trajectory_file}")
    poses = read_tum_trajectory(trajectory_file)
    logger.info(f"Loaded {len(poses)} estimated poses")
    
    if len(poses) == 0:
        logger.error("No poses loaded!")
        return False
    
    # Read associations from TUM dataset
    association_file = tum_data_path / dataset_name / "associations.txt"
    if not association_file.exists():
        logger.error(f"Association file not found: {association_file}")
        logger.error("Please generate associations.txt using associate.py")
        return False
    
    logger.info(f"Reading associations from: {association_file}")
    associations = read_tum_associations(association_file)
    logger.info(f"Loaded {len(associations)} RGB-D pairs")
    
    if len(associations) == 0:
        logger.error("No associations loaded!")
        return False
    
    # Get intrinsics
    intrinsic = get_tum_intrinsics(dataset_name)
    logger.info(f"Camera intrinsics: fx={intrinsic.intrinsic_matrix[0,0]:.1f}, "
                f"fy={intrinsic.intrinsic_matrix[1,1]:.1f}, "
                f"cx={intrinsic.intrinsic_matrix[0,2]:.1f}, "
                f"cy={intrinsic.intrinsic_matrix[1,2]:.1f}")
    
    # Create TSDF volume
    logger.info(f"\nInitializing TSDF volume:")
    logger.info(f"  Voxel size: {voxel_size}m")
    logger.info(f"  SDF truncation: {sdf_trunc}m")
    
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size,
        sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    # Integrate frames
    dataset_path = tum_data_path / dataset_name
    num_frames = len(associations)
    integrated_count = 0
    skipped_no_pose = 0
    skipped_no_file = 0
    
    logger.info(f"\nIntegrating frames (total={num_frames}, stride={stride})...")
    
    for i in range(0, num_frames, stride):
        rgb_timestamp, rgb_file, depth_timestamp, depth_file = associations[i]
        
        # Find closest estimated pose
        pose = find_closest_pose(rgb_timestamp, poses)
        if pose is None:
            skipped_no_pose += 1
            if skipped_no_pose <= 5:  # Only log first few
                print(f"DEBUG: Frame {i}: No matching pose (skipped) - Ts: {rgb_timestamp}")
                if i == 0:
                    print(f"DEBUG: First 5 poses keys: {list(poses.keys())[:5]}")
            continue
        
        # Prepare paths
        rgb_path = dataset_path / rgb_file
        
        # Handle Rendered Depth vs GT Depth
        if use_rendered_depth:
            # 1. Provide lazy loading of mapping to avoid overhead on failure
            if 'kfid_map' not in locals():
                # Find result directory with highest iteration (shutdown)
                shutdown_dirs = list(result_dir.glob("*_shutdown"))
                if not shutdown_dirs:
                    # Fallback to just finding numeric directories if shutdown not found
                    all_subdirs = [d for d in result_dir.iterdir() if d.is_dir() and d.name[0].isdigit()]
                    if not all_subdirs:
                        logger.error("No iteration directories found in result path!")
                        return False
                    # Sort by iteration number
                    result_subdir = sorted(all_subdirs, key=lambda x: int(x.name.split('_')[0]))[-1]
                else:
                    result_subdir = shutdown_dirs[0]
                
                logger.info(f"Using result directory: {result_subdir}")
                
                # Load cameras.json to map filename -> KFID
                cameras_json_path = result_subdir / "ply" / "cameras.json"
                if not cameras_json_path.exists():
                    logger.error(f"cameras.json not found at {cameras_json_path}")
                    return False
                
                with open(cameras_json_path, 'r') as f:
                    cameras_data = json.load(f)
                
                # Create map: img_name (basename) -> id
                kfid_map = {}
                for cam in cameras_data:
                    # img_name usually is the filename like "1305...png" or just "1305..."
                    # Check first item to see format
                    name = cam['img_name']
                    kfid_map[name] = cam['id']
                
                logger.info(f"Loaded {len(kfid_map)} keyframes from cameras.json")
                
                iteration_str = result_subdir.name.split('_')[0]
                depth_dir_base = result_subdir / "depth"
            
            # 2. Match current frame to keyframe
            rgb_basename = Path(rgb_file).name
            
            # Try exact match, basename, or full relative path
            kfid = kfid_map.get(rgb_basename)
            if kfid is None:
                kfid = kfid_map.get(Path(rgb_basename).stem)
            if kfid is None:
                kfid = kfid_map.get(rgb_file) # Check rgb/filename.png
            
            if kfid is None:
                # This frame is not a keyframe, skip it
                skipped_no_pose += 1
                if skipped_no_pose <= 5:
                    logger.debug(f"  Frame {i}: Not a keyframe (skipped) - Ts: {rgb_timestamp}")
                # Let's count it as valid skip
                continue
                
            # 3. Construct depth path: ITERATION_KFID_depth.png
            depth_filename = f"{iteration_str}_{kfid}_depth.png"
            depth_path = depth_dir_base / depth_filename
            
            if not depth_path.exists():
                # Try finding partial match if format differs
                # pattern = f"*_{kfid}_depth.png" ...
                logger.warning(f"Depth file missing for KF {kfid}: {depth_path}")
                skipped_no_file += 1
                continue
                
        else:
            # GT Depth
            depth_path = dataset_path / depth_file
            
            if not rgb_path.exists() or not depth_path.exists():
                skipped_no_file += 1
                if skipped_no_file <= 5:
                    logger.debug(f"  Frame {i}: Image files not found (skipped)")
                continue
        
        try:
            color = o3d.io.read_image(str(rgb_path))
            depth_img = o3d.io.read_image(str(depth_path))
            
            # For rendered depth, it is already 16-bit PNG scaled by 5000 (TUM format)
            # So logic below should be same: depth_scale=5000.0

            
            # Create RGBD image
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth_img,
                depth_scale=depth_scale,
                depth_trunc=depth_trunc,
                convert_rgb_to_intensity=False
            )
            
            # Integrate into TSDF
            # Open3D expects camera-to-world transform, so invert the pose
            volume.integrate(
                rgbd,
                intrinsic,
                np.linalg.inv(pose)
            )
            
            integrated_count += 1
            
            if (i + 1) % 100 == 0:
                logger.info(f"  Processed {i + 1}/{num_frames} frames "
                           f"({integrated_count} integrated)")
        
        except Exception as e:
            logger.warning(f"  Frame {i}: Integration error - {e}")
            continue
    
    logger.info(f"\nIntegration summary:")
    logger.info(f"  Total frames: {num_frames}")
    logger.info(f"  Integrated: {integrated_count}")
    logger.info(f"  Skipped (no pose): {skipped_no_pose}")
    logger.info(f"  Skipped (no file): {skipped_no_file}")
    
    if integrated_count == 0:
        logger.error("No frames were integrated!")
        return False
    
    # Extract mesh
    logger.info("\nExtracting triangle mesh...")
    try:
        mesh = volume.extract_triangle_mesh()
        mesh.compute_vertex_normals()
        
        logger.info(f"Mesh statistics:")
        logger.info(f"  Vertices: {len(mesh.vertices):,}")
        logger.info(f"  Triangles: {len(mesh.triangles):,}")
        
        # Save mesh
        output_mesh_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"\nSaving mesh to: {output_mesh_path}")
        o3d.io.write_triangle_mesh(str(output_mesh_path), mesh)
        
        # Get file size
        file_size = output_mesh_path.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"File size: {file_size:.1f} MB")
        
        logger.info("✅ Success!")
        return True
        
    except Exception as e:
        logger.error(f"Error extracting/saving mesh: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Generate TSDF meshes for Photo-SLAM PA experiments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate meshes for all PA variants
  python generate_pa_meshes.py --all
  
  # Generate meshes for specific PA variants
  python generate_pa_meshes.py --pa PA6 PA7 PA8
  
  # High quality meshes (5mm voxels)
  python generate_pa_meshes.py --all --voxel_size 0.005
  
  # Use specific run index
  python generate_pa_meshes.py --all --run_index 0
        """
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate meshes for all PA variants'
    )
    parser.add_argument(
        '--pa',
        type=str,
        nargs='+',
        help='Specific PA variants to process (e.g., PA6 PA7)'
    )
    parser.add_argument(
        '--data_path',
        type=str,
        default='/media/tam/DATA/data/TUM',
        help='Path to TUM dataset directory (default: /media/tam/DATA/data/TUM)'
    )
    parser.add_argument(
        '--results_base',
        type=str,
        default='/media/tam/DATA/3D/CG-photo',
        help='Base path for PA results (default: /media/tam/DATA/3D/CG-photo)'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default='/media/tam/DATA/3D/CG-photo/meshes_pa',
        help='Output directory for meshes (default: meshes_pa/)'
    )
    parser.add_argument(
        '--voxel_size',
        type=float,
        default=0.01,
        help='TSDF voxel size in meters (default: 0.01 = 1cm, use 0.005 for high quality)'
    )
    parser.add_argument(
        '--sdf_trunc',
        type=float,
        default=0.04,
        help='TSDF truncation distance in meters (default: 0.04)'
    )
    parser.add_argument(
        '--stride',
        type=int,
        default=1,
        help='Frame stride (1=all frames, 2=every other frame, etc.)'
    )
    parser.add_argument(
        '--run_index',
        type=int,
        default=0,
        help='Which run to use for mesh generation (0-9, default: 0)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    

    parser.add_argument(
        '--use_rendered_depth',
        action='store_true',
        help='Use rendered depth maps from Photo-SLAM instead of GT depth'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Determine which PA variants to process
    if args.all:
        pa_list = list(PA_VARIANTS.keys())
    elif args.pa:
        pa_list = [pa.upper() if not pa.upper().startswith('PA') else pa.upper() 
                   for pa in args.pa]
        # Validate PA names
        invalid = [pa for pa in pa_list if pa not in PA_VARIANTS]
        if invalid:
            logger.error(f"Invalid PA names: {invalid}")
            logger.error(f"Valid options: {list(PA_VARIANTS.keys())}")
            sys.exit(1)
    else:
        logger.error("Please specify --all or --pa <PA_NAME(S)>")
        parser.print_help()
        sys.exit(1)
    
    # Convert paths
    tum_data_path = Path(args.data_path)
    results_base = Path(args.results_base)
    output_dir = Path(args.output_dir)
    
    # Validate paths
    if not tum_data_path.exists():
        logger.error(f"TUM data path not found: {tum_data_path}")
        sys.exit(1)
    
    # Print configuration
    logger.info("="*60)
    logger.info("Photo-SLAM PA Mesh Generation")
    logger.info("="*60)
    logger.info(f"PA variants: {pa_list}")
    logger.info(f"TUM datasets: {TUM_DATASETS}")
    logger.info(f"Data path: {tum_data_path}")
    logger.info(f"Results base: {results_base}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Voxel size: {args.voxel_size}m")
    logger.info(f"SDF truncation: {args.sdf_trunc}m")
    logger.info(f"Stride: {args.stride}")
    logger.info(f"Run index: {args.run_index}")
    logger.info(f"Use rendered depth: {args.use_rendered_depth}")
    logger.info("="*60)
    
    # Process each PA variant
    total_meshes = len(pa_list) * len(TUM_DATASETS)
    current = 0
    success_count = 0
    failed = []
    
    for pa_name in pa_list:
        pa_info = PA_VARIANTS[pa_name]
        logger.info(f"\n{'#'*60}")
        logger.info(f"Processing {pa_name}: {pa_info['description']}")
        logger.info(f"{'#'*60}")
        
        pa_result_path = results_base / f"results_{pa_name.lower()}"
        
        if not pa_result_path.exists():
            logger.warning(f"Results path not found: {pa_result_path}")
            logger.warning(f"Skipping {pa_name}")
            continue
        
        for dataset_name in TUM_DATASETS:
            current += 1
            
            # Determine dataset short name for output
            if 'freiburg1' in dataset_name:
                dataset_short = 'fr1_desk'
            elif 'freiburg2' in dataset_name:
                dataset_short = 'fr2_xyz'
            elif 'freiburg3' in dataset_name:
                dataset_short = 'fr3_long'
            else:
                dataset_short = dataset_name
            
            # Output mesh path
            suffix = "_rendered" if args.use_rendered_depth else "_gt"
            mesh_filename = f"{pa_name.lower()}_{dataset_short}_run{args.run_index}{suffix}.ply"
            output_mesh_path = output_dir / pa_name.lower() / mesh_filename
            
            # Check if mesh already exists
            if output_mesh_path.exists():
                logger.info(f"\n[{current}/{total_meshes}] Mesh already exists: {mesh_filename}")
                logger.info("Skipping (use --force to regenerate)")
                success_count += 1
                continue
            
            logger.info(f"\n[{current}/{total_meshes}] Generating: {mesh_filename}")
            
            # Create mesh
            success = create_mesh_from_pa_result(
                pa_name=pa_name,
                dataset_name=dataset_name,
                tum_data_path=tum_data_path,
                pa_result_path=pa_result_path,
                output_mesh_path=output_mesh_path,
                voxel_size=args.voxel_size,
                sdf_trunc=args.sdf_trunc,
                stride=args.stride,
                run_index=args.run_index,
                use_rendered_depth=args.use_rendered_depth
            )
            
            if success:
                success_count += 1
            else:
                failed.append((pa_name, dataset_name))
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    logger.info(f"Total meshes: {total_meshes}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {len(failed)}")
    
    if failed:
        logger.info("\nFailed meshes:")
        for pa_name, dataset_name in failed:
            logger.info(f"  - {pa_name} / {dataset_name}")
    
    logger.info(f"\nOutput directory: {output_dir}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
