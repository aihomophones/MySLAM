#!/usr/bin/env python3
"""
Analyze and print mesh statistics.

Usage:
    python analyze_mesh.py ../meshes/freiburg1_desk_kinect.ply
"""

import open3d as o3d
import numpy as np
import argparse


def analyze_mesh(mesh_path):
    """Load and analyze a mesh file."""
    print(f"Loading mesh from: {mesh_path}")
    print("=" * 60)
    
    # Read mesh
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # Basic info
    print(f"\n📊 MESH STATISTICS:")
    print(f"  Vertices: {len(mesh.vertices):,}")
    print(f"  Triangles: {len(mesh.triangles):,}")
    print(f"  Has vertex colors: {mesh.has_vertex_colors()}")
    print(f"  Has vertex normals: {mesh.has_vertex_normals()}")
    
    # Compute bounds
    vertices = np.asarray(mesh.vertices)
    bbox_min = vertices.min(axis=0)
    bbox_max = vertices.max(axis=0)
    bbox_size = bbox_max - bbox_min
    
    print(f"\n📦 BOUNDING BOX:")
    print(f"  Min: [{bbox_min[0]:.2f}, {bbox_min[1]:.2f}, {bbox_min[2]:.2f}]")
    print(f"  Max: [{bbox_max[0]:.2f}, {bbox_max[1]:.2f}, {bbox_max[2]:.2f}]")
    print(f"  Size: [{bbox_size[0]:.2f}, {bbox_size[1]:.2f}, {bbox_size[2]:.2f}] meters")
    print(f"  Volume: {bbox_size[0] * bbox_size[1] * bbox_size[2]:.2f} m³")
    
    # Compute surface area
    if not mesh.has_triangle_normals():
        mesh.compute_triangle_normals()
    
    triangles = np.asarray(mesh.triangles)
    tri_verts = vertices[triangles]
    v0, v1, v2 = tri_verts[:, 0], tri_verts[:, 1], tri_verts[:, 2]
    areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    total_area = areas.sum()
    
    print(f"\n📐 SURFACE:")
    print(f"  Total surface area: {total_area:.2f} m²")
    print(f"  Average triangle area: {total_area / len(triangles):.6f} m²")
    
    # Check for manifold
    mesh_clean = mesh.remove_duplicated_vertices()
    mesh_clean = mesh_clean.remove_duplicated_triangles()
    mesh_clean = mesh_clean.remove_degenerate_triangles()
    
    print(f"\n🔧 MESH QUALITY:")
    print(f"  Is edge manifold: {mesh.is_edge_manifold()}")
    print(f"  Is vertex manifold: {mesh.is_vertex_manifold()}")
    print(f"  Is watertight: {mesh.is_watertight()}")
    
    print("=" * 60)
    print("✅ Analysis complete!")


def main():
    parser = argparse.ArgumentParser(description="Analyze mesh files")
    parser.add_argument("mesh_file", help="Path to mesh file (.ply, .obj, etc.)")
    
    args = parser.parse_args()
    analyze_mesh(args.mesh_file)


if __name__ == "__main__":
    main()
