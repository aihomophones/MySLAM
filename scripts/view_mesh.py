#!/usr/bin/env python3
"""
Simple mesh viewer using Open3D.

Usage:
    python view_mesh.py ../meshes/freiburg1_desk_kinect.ply
"""

import open3d as o3d
import argparse


def view_mesh(mesh_path):
    """Load and visualize a mesh file."""
    print(f"Loading mesh from: {mesh_path}")
    
    # Read mesh
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # Print mesh info
    print(f"Vertices: {len(mesh.vertices):,}")
    print(f"Triangles: {len(mesh.triangles):,}")
    print(f"Has vertex colors: {mesh.has_vertex_colors()}")
    print(f"Has vertex normals: {mesh.has_vertex_normals()}")
    
    # Compute normals if not present
    if not mesh.has_vertex_normals():
        print("Computing vertex normals...")
        mesh.compute_vertex_normals()
    
    # Visualize
    print("\nOpening viewer... (Press Q to quit)")
    o3d.visualization.draw_geometries(
        [mesh],
        mesh_show_wireframe=False,
        mesh_show_back_face=True,
        window_name=f"Mesh Viewer - {mesh_path}"
    )


def main():
    parser = argparse.ArgumentParser(description="View mesh files with Open3D")
    parser.add_argument("mesh_file", help="Path to mesh file (.ply, .obj, etc.)")
    
    args = parser.parse_args()
    view_mesh(args.mesh_file)


if __name__ == "__main__":
    main()
