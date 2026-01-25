#!/usr/bin/env python3
"""
Generate mesh from Gaussian point cloud (centers) using Poisson reconstruction.
"""

import numpy as np
import open3d as o3d
from pathlib import Path
from plyfile import PlyData
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()


def create_mesh_from_gaussians(result_dir: Path, output_path: Path, depth: int = 9):
    """Create mesh from Gaussian centers using Poisson reconstruction."""
    
    # Find Gaussian PLY file
    ply_files = list(result_dir.glob('*_shutdown/ply/*.ply'))
    if not ply_files:
        raise FileNotFoundError(f"No PLY files found in {result_dir}")
    
    ply_path = ply_files[0]
    logger.info(f'Loading Gaussians: {ply_path}')
    
    # Read PLY
    plydata = PlyData.read(str(ply_path))
    xyz = np.stack([
        plydata['vertex']['x'],
        plydata['vertex']['y'],
        plydata['vertex']['z']
    ], axis=1)
    
    logger.info(f'Loaded {len(xyz)} Gaussian centers')
    
    # Create point cloud
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    
    # Estimate normals (required for Poisson)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(k=15)
    
    logger.info('Creating mesh with Poisson reconstruction...')
    
    # Poisson surface reconstruction
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth, linear_fit=False
    )
    
    # Remove low-density vertices (noise)
    densities = np.asarray(densities)
    threshold = np.quantile(densities, 0.02)
    vertices_to_remove = densities < threshold
    mesh.remove_vertices_by_mask(vertices_to_remove)
    
    mesh.compute_vertex_normals()
    
    # Save mesh
    output_path.parent.mkdir(parents=True, exist_ok=True)
    o3d.io.write_triangle_mesh(str(output_path), mesh)
    logger.info(f'Saved mesh: {output_path} ({len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles)')
    
    return mesh


def main():
    parser = argparse.ArgumentParser(description='Create mesh from Gaussian point cloud')
    parser.add_argument('--result_dir', required=True, help='Path to PA6 results (contains *_shutdown/ply/)')
    parser.add_argument('--output', required=True, help='Output mesh path')
    parser.add_argument('--depth', type=int, default=9, help='Poisson reconstruction depth (higher=more detail)')
    args = parser.parse_args()
    
    create_mesh_from_gaussians(Path(args.result_dir), Path(args.output), args.depth)


if __name__ == '__main__':
    main()
