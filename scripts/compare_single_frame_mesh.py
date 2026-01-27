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


def create_mesh_from_points(points, output_path, depth_values=None, method='poisson', camera_center=None):
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
    if camera_center is not None:
        pcd.orient_normals_towards_camera_location(camera_center)
    else:
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
    parser.add_argument('--gt_frame_id', type=int, default=None, help='GT Frame ID if different from frame_id')
    args = parser.parse_args()
    
    # Replica camera intrinsics
    intrinsics = {'fx': 600.0, 'fy': 600.0, 'cx': 599.5, 'cy': 339.5}
    
    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine GT Frame ID
    gt_fid = args.gt_frame_id if args.gt_frame_id is not None else args.frame_id
    
    # Load GT pose for this frame
    gt_poses = {}
    with open(args.gt_traj, 'r') as f:
        for i, line in enumerate(f):
            values = [float(x) for x in line.strip().split()]
            if len(values) == 16:
                gt_poses[i] = np.array(values).reshape(4, 4)
    
    pose = gt_poses.get(gt_fid)
    if pose is None:
        print(f"Pose for frame {gt_fid} not found!")
        return
    
    # Load rendered depth
    # Load rendered depth - Prioritize 'depth' folder (original keyframes)
    render_depth_dirs = []
    # Check 'depth' folder first
    depth_dirs = list(result_dir.glob('*_shutdown/depth'))
    if depth_dirs:
        render_depth_dirs.extend(depth_dirs)
    
    # Check 'all_depths' folder second
    all_depths = list(result_dir.glob('*_shutdown/all_depths'))
    if all_depths:
        render_depth_dirs.extend(all_depths)
    
    render_depth_path = None
    for d in render_depth_dirs:
        # Try different naming patterns
        candidates = [
            f"*_{args.frame_id}_depth.png",  # Keyframe pattern: 2881_24_depth.png
            f"{args.frame_id}_depth.png"     # Simple pattern: 24_depth.png
        ]
        
        found = False
        for c in candidates:
            matches = list(d.glob(c))
            # Sort by name length to prefer exact matches or consistent patterns if multiple
            if matches:
                 # If keyframe pattern, pick one (usually only one). 
                 # If multiple matches (rare), pick the one with matching frame id explicit
                 # Here we just pick first found
                 render_depth_path = matches[0]
                 found = True
                 break
        if found:
            break
    
    if render_depth_path and render_depth_path.exists():
        print(f"Loading rendered depth: {render_depth_path}")
        render_depth = np.array(Image.open(render_depth_path)).astype(np.float32) / args.depth_scale
        render_points, render_depths = depth_to_pointcloud(render_depth, intrinsics, pose)
        create_mesh_from_points(render_points, output_dir / f"frame{args.frame_id}_rendered.ply", render_depths, camera_center=pose[:3, 3])
    else:
        print(f"Rendered depth not found for frame {args.frame_id}")
    
    # Load GT depth
    gt_depth_path = Path(args.gt_depth_dir) / f"depth{gt_fid:06d}.png"
    if gt_depth_path.exists():
        print(f"Loading GT depth: {gt_depth_path}")
        gt_depth = np.array(Image.open(gt_depth_path)).astype(np.float32) / args.depth_scale
        gt_points, gt_depths = depth_to_pointcloud(gt_depth, intrinsics, pose)
        create_mesh_from_points(gt_points, output_dir / f"frame{args.frame_id}_gt.ply", gt_depths, camera_center=pose[:3, 3])
    else:
        print(f"GT depth not found: {gt_depth_path}")


if __name__ == '__main__':
    main()
