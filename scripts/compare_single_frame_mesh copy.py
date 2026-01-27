#!/usr/bin/env python3
"""
Generate point cloud mesh from a single frame depth map.
Creates two meshes: one from rendered depth, one from GT depth.
Output can be compared in MeshLab.
"""

import numpy as np
import open3d as o3d
from PIL import Image
import argparse
from pathlib import Path
import re


def umeyama_alignment(x, y, with_scale=True):
    """Umeyama alignment: y = s * R @ x + t"""
    n = x.shape[0]
    mu_x, mu_y = x.mean(0), y.mean(0)
    x_c, y_c = x - mu_x, y - mu_y
    
    cov = y_c.T @ x_c / n
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    
    s = np.trace(np.diag(D) @ S) / np.var(x_c, axis=0).sum() if with_scale else 1.0
    t = mu_y - s * R @ mu_x
    return R, t, s


def read_tum_trajectory(traj_file):
    poses = {}
    with open(traj_file, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            frame_id = int(float(parts[0]))
            tx, ty, tz = float(parts[1]), float(parts[2]), float(parts[3])
            qx, qy, qz, qw = float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])
            R = o3d.geometry.get_rotation_matrix_from_quaternion([qw, qx, qy, qz])
            pose = np.eye(4)
            pose[:3, :3], pose[:3, 3] = R, [tx, ty, tz]
            poses[frame_id] = pose
    return poses


def depth_to_pointcloud(depth_img, intrinsics, pose=None):
    """Convert depth image to point cloud."""
    H, W = depth_img.shape
    fx, fy = intrinsics['fx'], intrinsics['fy']
    cx, cy = intrinsics['cx'], intrinsics['cy']
    
    # Create pixel grid
    u = np.arange(W)
    v = np.arange(H)
    u, v = np.meshgrid(u, v)
    
    # Backproject to 3D
    z = depth_img
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    
    # Filter valid points
    valid = z > 0.1
    points = np.stack([x[valid], y[valid], z[valid]], axis=1)
    depth_vals = z[valid]
    
    # Apply pose if provided (transform to world coordinates)
    if pose is not None:
        R = pose[:3, :3]
        t = pose[:3, 3]
        points = points @ R.T + t
    
    return points, depth_vals


def create_mesh_from_points(points, output_path, depth_values=None, method='poisson'):
    """Create mesh from point cloud."""
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    
    # Add color based on depth (blue=near, red=far)
    if depth_values is not None:
        z_min, z_max = np.percentile(depth_values, [5, 95])
        z_norm = np.clip((depth_values - z_min) / (z_max - z_min + 1e-6), 0, 1)
        # Blue (near) -> Green -> Red (far)
        colors = np.zeros((len(depth_values), 3))
        colors[:, 0] = z_norm  # R increases with depth
        colors[:, 1] = 1 - np.abs(z_norm - 0.5) * 2  # G highest at middle
        colors[:, 2] = 1 - z_norm  # B decreases with depth
        pcd.colors = o3d.utility.Vector3dVector(colors)
    
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(k=15)
    
    if method == 'poisson':
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
        # Remove low-density vertices
        densities = np.asarray(densities)
        vertices_to_remove = densities < np.quantile(densities, 0.01)
        mesh.remove_vertices_by_mask(vertices_to_remove)
    else:
        # Ball pivoting
        radii = [0.01, 0.02, 0.04]
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii))
    
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    print(f"Saved mesh: {output_path} ({len(mesh.vertices)} vertices)")
    
    # Also save point cloud
    pcd_path = output_path.with_suffix('.pcd')
    o3d.io.write_point_cloud(str(pcd_path), pcd)
    print(f"Saved point cloud: {pcd_path}")
    
    return mesh


def main():
    parser = argparse.ArgumentParser(description='Generate mesh from single frame depth')
    parser.add_argument('--frame_id', type=int, default=0, help='Frame ID to process')
    parser.add_argument('--result_dir', type=str, required=True, help='Photo-SLAM result directory')
    parser.add_argument('--gt_depth_dir', type=str, required=True, help='GT depth directory')
    parser.add_argument('--gt_traj', type=str, required=True, help='GT trajectory file')
    parser.add_argument('--output_dir', type=str, required=True, help='Output directory')
    parser.add_argument('--depth_scale', type=float, default=6553.5, help='Depth scale')
    args = parser.parse_args()
    
    # Replica camera intrinsics
    intrinsics = {'fx': 600.0, 'fy': 600.0, 'cx': 599.5, 'cy': 339.5}
    
    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load GT pose for this frame
    gt_poses = {}
    with open(args.gt_traj, 'r') as f:
        for i, line in enumerate(f):
            values = [float(x) for x in line.strip().split()]
            if len(values) == 16:
                gt_poses[i] = np.array(values).reshape(4, 4)
    
    pose_gt = gt_poses.get(args.frame_id)
    if pose_gt is None:
        print(f"GT Pose for frame {args.frame_id} not found!")
        return

    # Load and Align Estimated Poses
    tum_traj_path = result_dir / "CameraTrajectory_TUM.txt"
    pose_est = None
    if tum_traj_path.exists():
        print(f"Loading estimated trajectory: {tum_traj_path}")
        est_poses = read_tum_trajectory(tum_traj_path)
        
        # Align est to gt
        common = sorted(set(est_poses.keys()) & set(gt_poses.keys()))
        if common:
            # Use max 500 frames for alignment
            common_align = common[:500] 
            est_pos = np.array([est_poses[i][:3, 3] for i in common_align])
            gt_pos = np.array([gt_poses[i][:3, 3] for i in common_align])
            
            R_align, t_align, s_align = umeyama_alignment(est_pos, gt_pos, with_scale=True)
            print(f"Aligned trajectories (Scale={s_align:.4f})")
            
            # Get aligned pose for target frame
            if args.frame_id in est_poses:
                raw_pose = est_poses[args.frame_id]
                aligned_pose = np.eye(4)
                aligned_pose[:3, :3] = T_align_R = s_align * R_align @ raw_pose[:3, :3] / s_align # Scale rotation? No, rotation is scale-invariant usually, but position scales.
                # Actually P_new = s * R * P_old + t
                # For pose matrix T = [R | t]:
                # R_new = R_align * R_old
                # t_new = s * R_align * t_old + t_align
                
                # Re-calculate correct transformation
                # Top-left 3x3 of pose is Rotation (scale independent)
                # But if we scale the world, the translation scales.
                
                # Correct way for Sim3:
                # T_align = [sR, t]
                # p_world_gt = T_align * p_world_est
                # But poses are camera-to-world (or world-to-camera?)
                # TUM format is usually Camera-to-World (position of camera in world).
                # So P_cam_gt = T_align * P_cam_est
                
                new_R = R_align @ raw_pose[:3, :3]
                new_t = s_align * R_align @ raw_pose[:3, 3] + t_align
                
                pose_est = np.eye(4)
                pose_est[:3, :3] = new_R
                pose_est[:3, 3] = new_t
                print(f"Using Aligned Estimated Pose for Frame {args.frame_id}")
            else:
                 print(f"Frame {args.frame_id} not found in estimated trajectory!")
        else:
            print("No common frames found for alignment!")
    else:
        print("CameraTrajectory_TUM.txt not found. Using GT pose for render.")
        pose_est = pose_gt

    if pose_est is None:
        pose_est = pose_gt
    
    # Load rendered depth
    render_depth_dirs = list(result_dir.glob('*_shutdown/all_depths'))
    if not render_depth_dirs:
        render_depth_dirs = list(result_dir.glob('*_shutdown/depth'))
    
    render_depth_path = None
    for d in render_depth_dirs:
        candidates = [
            d / f"{args.frame_id}_depth.png",
            d / f"*_{args.frame_id}_depth.png"
        ]
        for c in candidates:
            matches = list(d.glob(c.name)) if '*' in str(c) else ([c] if c.exists() else [])
            if matches:
                render_depth_path = matches[0]
                break
    
    # Fallback to any available depth file if specific frame not found
    if not render_depth_path and render_depth_dirs:
        all_files = list(render_depth_dirs[0].glob('*.png'))
        if all_files:
            render_depth_path = all_files[0]
            print(f"WARNING: Exact match for frame {args.frame_id} not found. Using fallback: {render_depth_path.name}")
    
    # Check in main result dir for eval outputs (*_depth_raw.png)
    if not render_depth_path:
        candidates = list(result_dir.glob(f'*_{args.frame_id}_depth_raw.png'))
        if candidates:
            render_depth_path = candidates[0]
            print(f"Found depth in result dir: {render_depth_path.name}")
        else:
            # Fallback in main dir
            all_raw = list(result_dir.glob('*_depth_raw.png'))
            if all_raw:
                render_depth_path = all_raw[0]
                # Try to extract frame ID from filename: iter_frameID_depth_raw.png
                parts = render_depth_path.name.split('_')
                if len(parts) >= 2 and parts[1].isdigit():
                    args.frame_id = int(parts[1])
                    print(f"WARNING: Using fallback frame {args.frame_id} from {render_depth_path.name}")
    
    if render_depth_path and render_depth_path.exists():
        print(f"Loading rendered depth: {render_depth_path}")
        render_depth = np.array(Image.open(render_depth_path)).astype(np.float32) / args.depth_scale
        # Use pose_est for rendered mesh
        render_points, render_depths = depth_to_pointcloud(render_depth, intrinsics, pose_est)
        create_mesh_from_points(render_points, output_dir / f"frame{args.frame_id}_rendered.ply", render_depths)
    else:
        print(f"Rendered depth not found for frame {args.frame_id}")
    
    # Load GT depth
    gt_depth_path = Path(args.gt_depth_dir) / f"depth{args.frame_id:06d}.png"
    if gt_depth_path.exists():
        print(f"Loading GT depth: {gt_depth_path}")
        gt_depth = np.array(Image.open(gt_depth_path)).astype(np.float32) / args.depth_scale
        # Always use GT pose for GT mesh
        gt_points, gt_depths = depth_to_pointcloud(gt_depth, intrinsics, pose_gt)
        create_mesh_from_points(gt_points, output_dir / f"frame{args.frame_id}_gt.ply", gt_depths)
    else:
        print(f"GT depth not found: {gt_depth_path}")


if __name__ == '__main__':
    main()
