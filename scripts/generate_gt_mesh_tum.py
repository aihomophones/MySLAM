import argparse
import os
import shutil
import numpy as np
import open3d as o3d
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from scipy.spatial.transform import Rotation as R

def load_tum_groundtruth(gt_path):
    """
    Load TUM groundtruth.txt.
    Format: timestamp tx ty tz qx qy qz qw
    Returns: dict {timestamp: (tx, ty, tz, qx, qy, qz, qw)}
    """
    print(f"Loading ground truth from {gt_path}...")
    gt_poses = {}
    with open(gt_path, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if not parts:
                continue
            t = float(parts[0])
            # tx ty tz qx qy qz qw
            data = np.array([float(x) for x in parts[1:]])
            gt_poses[t] = data
    print(f"Loaded {len(gt_poses)} GT poses.")
    return gt_poses

def load_tum_depth_list(depth_file_path):
    """
    Load depth.txt.
    Format: timestamp filename
    Returns: list of (timestamp, filename)
    """
    print(f"Loading depth list from {depth_file_path}...")
    depth_list = []
    with open(depth_file_path, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if not parts:
                continue
            t = float(parts[0])
            filename = parts[1]
            depth_list.append((t, filename))
    print(f"Loaded {len(depth_list)} depth frames.")
    return depth_list

def associate(depth_list, gt_poses, max_diff=0.02):
    """
    Associate depth frames with GT poses based on timestamp.
    Returns: list of (depth_timestamp, depth_filename, gt_pose_data)
    """
    matches = []
    gt_timestamps = np.array(list(gt_poses.keys()))
    gt_timestamps.sort()
    
    for d_t, d_file in depth_list:
        # Find closest GT timestamp
        idx = np.searchsorted(gt_timestamps, d_t)
        
        candidates = []
        if idx < len(gt_timestamps):
            candidates.append(gt_timestamps[idx])
        if idx > 0:
            candidates.append(gt_timestamps[idx-1])
            
        if not candidates:
            continue
            
        best_t = min(candidates, key=lambda x: abs(x - d_t))
        diff = abs(best_t - d_t)
        
        if diff < max_diff:
            matches.append((d_t, d_file, gt_poses[best_t]))
            
    print(f"Associated {len(matches)} depth frames with GT poses (max_diff={max_diff}s).")
    return matches

def get_intrinsic_matrix(scene_name):
    # TUM Intrinsics (approximate values based on dataset descriptions)
    # fr1: focal length ~517, center ~318, 255
    # fr2: focal length ~520, center ~325, 250
    # fr3: focal length ~535, center ~320, 240
    # Ideally should read from calibration files if available, but for now hardcode based on standard TUM sets.
    
    if "freiburg1" in scene_name:
        fx, fy = 517.3, 516.5
        cx, cy = 318.6, 255.3
    elif "freiburg2" in scene_name:
        fx, fy = 520.9, 521.0
        cx, cy = 325.1, 249.7
    elif "freiburg3" in scene_name:
        fx, fy = 535.4, 539.2
        cx, cy = 320.1, 247.6
    else:
        print("Warning: Unknown camera calibration, using fr1 defaults.")
        fx, fy = 517.3, 516.5
        cx, cy = 318.6, 255.3
        
    width, height = 640, 480
    return o3d.camera.PinholeCameraIntrinsic(width, height, fx, fy, cx, cy)

def main():
    parser = argparse.ArgumentParser(description='Generate GT mesh for TUM dataset using TSDF integration')
    parser.add_argument('--sequence_dir', type=str, required=True, help='Path to TUM sequence directory (containing rgb, depth, groundtruth.txt)')
    parser.add_argument('--output', type=str, default='gt_mesh.ply', help='Output mesh path')
    parser.add_argument('--stride', type=int, default=5, help='Frame stride (process every Nth frame)')
    parser.add_argument('--voxel_size', type=float, default=0.01, help='Voxel size')
    parser.add_argument('--depth_scale', type=float, default=5000.0, help='Depth scale factor')
    parser.add_argument('--max_depth', type=float, default=3.5, help='Max depth truncation (meters)')
    
    args = parser.parse_args()
    
    sequence_path = Path(args.sequence_dir)
    gt_path = sequence_path / "groundtruth.txt"
    depth_list_path = sequence_path / "depth.txt"
    
    if not gt_path.exists():
        print(f"Error: {gt_path} not found.")
        return
    if not depth_list_path.exists():
        print(f"Error: {depth_list_path} not found.")
        return
        
    # 1. Load Data
    gt_poses = load_tum_groundtruth(gt_path)
    depth_list = load_tum_depth_list(depth_list_path)
    
    # 2. Keyframe Selection (Assume whole sequence with stride)
    # Associate first
    matches = associate(depth_list, gt_poses)
    
    # Apply stride
    matches = matches[::args.stride]
    print(f"Processing {len(matches)} frames after stride {args.stride}.")
    
    # 3. TSDF Integration
    intrinsic = get_intrinsic_matrix(sequence_path.name)
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=args.voxel_size,
        sdf_trunc=args.voxel_size * 5,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.NoColor
    )
    
    for d_t, d_rel_path, pose_data in tqdm(matches, desc="Integrating"):
        depth_path = sequence_path / d_rel_path
        if not depth_path.exists():
            continue
            
        # Pose: [tx ty tz qx qy qz qw] -> 4x4
        tx, ty, tz, qx, qy, qz, qw = pose_data
        rotation = R.from_quat([qx, qy, qz, qw]).as_matrix()
        translation = np.array([tx, ty, tz])
        
        Twc = np.eye(4)
        Twc[:3, :3] = rotation
        Twc[:3, 3] = translation
        
        # Open3D integrate takes Tcw (World to Camera)
        Tcw = np.linalg.inv(Twc)
        
        # Load Depth
        depth_img_raw = np.array(Image.open(depth_path))
        depth_o3d = o3d.geometry.Image(depth_img_raw)
        
        # Create Dummy Color
        h, w = depth_img_raw.shape
        color_o3d = o3d.geometry.Image(np.zeros((h, w, 3), dtype=np.uint8))
        
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d,
            depth_scale=args.depth_scale,
            depth_trunc=args.max_depth,
            convert_rgb_to_intensity=False
        )
        
        volume.integrate(rgbd, intrinsic, Tcw)
        
    # 4. Extract Mesh
    print("Extracting mesh...")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    print(f"Saved GT mesh to {output_path}")

if __name__ == "__main__":
    main()
