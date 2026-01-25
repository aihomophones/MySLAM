#!/usr/bin/env python3
"""
Generate mesh from Photo-SLAM PA6 depth + ALIGNED poses.
Aligns Photo-SLAM trajectory to GT trajectory using Umeyama, then creates mesh.
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
    'width': 1200, 'height': 680,
    'fx': 600.0, 'fy': 600.0, 'cx': 599.5, 'cy': 339.5
}


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


def read_replica_trajectory(traj_file):
    poses = {}
    with open(traj_file, 'r') as f:
        for i, line in enumerate(f):
            values = [float(x) for x in line.strip().split()]
            if len(values) == 16:
                poses[i] = np.array(values).reshape(4, 4)
    return poses


def find_depth_files(result_dir):
    depth_files = {}
    for sd in result_dir.glob("*_shutdown"):
        dd = sd / "depth"
        if dd.exists():
            for df in dd.glob("*_depth.png"):
                m = re.search(r'_(\d+)_depth\.png$', df.name)
                if m:
                    depth_files[int(m.group(1))] = df
    return depth_files


def create_mesh(result_dir, dataset_path, output_path, voxel_size=0.02, depth_scale=6553.5):
    # Load trajectories
    est_poses = read_tum_trajectory(result_dir / "CameraTrajectory_TUM.txt")
    gt_poses = read_replica_trajectory(dataset_path / "traj.txt")
    logger.info(f"Loaded {len(est_poses)} estimated, {len(gt_poses)} GT poses")
    
    # Align trajectories
    common = sorted(set(est_poses.keys()) & set(gt_poses.keys()))
    est_pos = np.array([est_poses[i][:3, 3] for i in common])
    gt_pos = np.array([gt_poses[i][:3, 3] for i in common])
    R, t, s = umeyama_alignment(est_pos, gt_pos, with_scale=True)
    logger.info(f"Alignment: scale={s:.4f}")
    
    # Apply alignment to poses
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = s * R, t
    aligned_poses = {}
    for fid, pose in est_poses.items():
        new_pose = np.eye(4)
        new_pose[:3, 3] = T[:3, :3] @ pose[:3, 3] + T[:3, 3]
        new_pose[:3, :3] = T[:3, :3] @ pose[:3, :3] / s
        aligned_poses[fid] = new_pose
    
    # Find depth files
    depth_files = find_depth_files(result_dir)
    logger.info(f"Found {len(depth_files)} depth files")
    
    # TSDF integration
    intrinsic = o3d.camera.PinholeCameraIntrinsic(
        REPLICA_INTRINSICS['width'], REPLICA_INTRINSICS['height'],
        REPLICA_INTRINSICS['fx'], REPLICA_INTRINSICS['fy'],
        REPLICA_INTRINSICS['cx'], REPLICA_INTRINSICS['cy']
    )
    volume = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_size, sdf_trunc=voxel_size*3,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
    )
    
    integrated = 0
    for fid, dp in sorted(depth_files.items()):
        if fid not in aligned_poses:
            continue
        try:
            depth = o3d.io.read_image(str(dp))
            color = o3d.geometry.Image(np.ones((680, 1200, 3), dtype=np.uint8) * 128)
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth, depth_scale=depth_scale, depth_trunc=10.0, convert_rgb_to_intensity=False
            )
            volume.integrate(rgbd, intrinsic, np.linalg.inv(aligned_poses[fid]))
            integrated += 1
        except Exception as e:
            logger.warning(f"Failed {fid}: {e}")
    
    logger.info(f"Integrated {integrated} frames")
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    logger.info(f"Saved: {output_path} ({len(mesh.vertices)} vertices)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--result_dir', required=True)
    parser.add_argument('--dataset_path', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--voxel_size', type=float, default=0.02)
    parser.add_argument('--depth_scale', type=float, default=6553.5)
    args = parser.parse_args()
    create_mesh(Path(args.result_dir), Path(args.dataset_path), Path(args.output),
                args.voxel_size, args.depth_scale)
