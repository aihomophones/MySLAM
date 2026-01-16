#!/usr/bin/env python3
"""
Depth-Photo-SLAM vs Photo-SLAM Comparison Script
Đọc 2 thư mục kết quả và tạo bảng so sánh markdown.

Usage:
    python compare_results.py --baseline results --method results_cg --output comparison.md
"""

import os
import argparse
import glob
import re
from pathlib import Path


def find_shutdown_dir(scene_path):
    """Tìm thư mục *_shutdown trong scene path."""
    shutdowns = glob.glob(os.path.join(scene_path, "*_shutdown"))
    return shutdowns[0] if shutdowns else None


def read_metric_file(filepath):
    """Đọc file metrics và tính trung bình."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r') as f:
            values = []
            for line in f:
                line = line.strip()
                # Skip header lines starting with ##
                if not line or line.startswith('#'):
                    continue
                # Format: "id value" hoặc just "value"
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        values.append(float(parts[1]))
                    except:
                        values.append(float(parts[0]))
                elif len(parts) == 1:
                    values.append(float(parts[0]))
        return sum(values) / len(values) if values else None
    except Exception as e:
        return None


def read_trajectory_metrics(scene_path):
    """Đọc metrics từ metrics_traj.txt (RMSE, ATE)."""
    metrics_file = os.path.join(scene_path, "metrics_traj.txt")
    if not os.path.exists(metrics_file):
        return {}
    
    results = {}
    try:
        with open(metrics_file, 'r') as f:
            content = f.read()
            
        # Tìm RMSE translation
        rmse_match = re.search(r'translation.*?rmse\s+([\d.]+)', content, re.DOTALL | re.IGNORECASE)
        if rmse_match:
            results['ate_rmse'] = float(rmse_match.group(1))
            
        # Tìm mean translation error
        mean_match = re.search(r'translation.*?mean\s+([\d.]+)', content, re.DOTALL | re.IGNORECASE)
        if mean_match:
            results['ate_mean'] = float(mean_match.group(1))
    except:
        pass
    
    return results


def count_gaussians(shutdown_dir):
    """Đếm số Gaussians từ file point_cloud.ply."""
    ply_files = glob.glob(os.path.join(shutdown_dir, "ply", "point_cloud", "*", "point_cloud.ply"))
    if not ply_files:
        ply_files = glob.glob(os.path.join(shutdown_dir, "ply", "*.ply"))
    if not ply_files:
        return None
    try:
        with open(ply_files[0], 'r', errors='ignore') as f:
            for line in f:
                if line.startswith("element vertex"):
                    return int(line.split()[2])
                if line.startswith("end_header"):
                    break
    except:
        pass
    return None


def get_scene_metrics(result_dir, iteration=0):
    """Lấy metrics cho tất cả scenes trong một iteration."""
    iter_dir = os.path.join(result_dir, f"tum_rgbd_{iteration}")
    if not os.path.exists(iter_dir):
        print(f"  Không tìm thấy: {iter_dir}")
        return {}
    
    metrics = {}
    for scene_name in os.listdir(iter_dir):
        scene_path = os.path.join(iter_dir, scene_name)
        if not os.path.isdir(scene_path):
            continue
        
        shutdown_dir = find_shutdown_dir(scene_path)
        if not shutdown_dir:
            continue
        
        # Đọc PSNR từ shutdown dir hoặc scene dir
        psnr_file = os.path.join(shutdown_dir, "psnr.txt")
        if not os.path.exists(psnr_file):
            psnr_file = os.path.join(scene_path, "psnr.txt")
        
        # SSIM có thể ở scene level
        ssim_file = os.path.join(scene_path, "ssim.txt")
        if not os.path.exists(ssim_file):
            ssim_file = os.path.join(shutdown_dir, "ssim.txt")
        
        # LPIPS ở scene level
        lpips_file = os.path.join(scene_path, "lpips.txt")
        if not os.path.exists(lpips_file):
            lpips_file = os.path.join(shutdown_dir, "lpips.txt")
        
        # DSSIM từ shutdown dir
        dssim_file = os.path.join(shutdown_dir, "dssim.txt")
        
        # Trajectory metrics
        traj_metrics = read_trajectory_metrics(scene_path)
        
        short_name = scene_name.replace("rgbd_dataset_", "")
        metrics[short_name] = {
            "psnr": read_metric_file(psnr_file),
            "ssim": read_metric_file(ssim_file),
            "lpips": read_metric_file(lpips_file),
            "dssim": read_metric_file(dssim_file),
            "gaussians": count_gaussians(shutdown_dir),
            "ate_rmse": traj_metrics.get('ate_rmse'),
            "ate_mean": traj_metrics.get('ate_mean'),
        }
        
        psnr_str = f"{metrics[short_name]['psnr']:.2f}" if metrics[short_name]['psnr'] else 'N/A'
        ssim_str = f"{metrics[short_name]['ssim']:.3f}" if metrics[short_name]['ssim'] else 'N/A'
        lpips_str = f"{metrics[short_name]['lpips']:.3f}" if metrics[short_name]['lpips'] else 'N/A'
        print(f"  {short_name}: psnr={psnr_str}, ssim={ssim_str}, lpips={lpips_str}, gaus={metrics[short_name]['gaussians']}")
    
    return metrics


def format_value(val, precision=2):
    """Format giá trị cho bảng."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{precision}f}"
    return str(val)


def generate_markdown(baseline_metrics, method_metrics, baseline_name="Photo-SLAM", method_name="Depth-Photo-SLAM"):
    """Tạo bảng markdown so sánh."""
    md = []
    md.append(f"# 📊 So sánh: {method_name} vs {baseline_name}")
    md.append("")
    md.append(f"*Generated automatically*")
    md.append("")
    
    all_scenes = sorted(set(baseline_metrics.keys()) | set(method_metrics.keys()))
    
    if not all_scenes:
        md.append("⚠️ Không tìm thấy dữ liệu để so sánh!")
        return "\n".join(md)
    
    # === PSNR Table ===
    md.append("## PSNR (dB) ↑ Càng cao càng tốt")
    md.append("")
    md.append(f"| Dataset | {baseline_name} | {method_name} | Δ |")
    md.append("|---------|------------|------------------|---|")
    
    for scene in all_scenes:
        base_val = baseline_metrics.get(scene, {}).get("psnr")
        meth_val = method_metrics.get(scene, {}).get("psnr")
        delta = ""
        if base_val and meth_val:
            diff = meth_val - base_val
            emoji = " ✅" if diff > 0 else (" ⚠️" if diff < -1 else "")
            delta = f"{diff:+.2f}{emoji}"
        meth_str = f"**{format_value(meth_val)}**" if base_val and meth_val and meth_val > base_val else format_value(meth_val)
        md.append(f"| {scene} | {format_value(base_val)} | {meth_str} | {delta} |")
    md.append("")
    
    # === SSIM Table ===
    md.append("## SSIM ↑ Càng cao càng tốt")
    md.append("")
    md.append(f"| Dataset | {baseline_name} | {method_name} | Δ |")
    md.append("|---------|------------|------------------|---|")
    
    for scene in all_scenes:
        base_val = baseline_metrics.get(scene, {}).get("ssim")
        meth_val = method_metrics.get(scene, {}).get("ssim")
        delta = ""
        if base_val and meth_val:
            diff = meth_val - base_val
            emoji = " ✅" if diff > 0 else (" ⚠️" if diff < -0.01 else "")
            delta = f"{diff:+.4f}{emoji}"
        meth_str = f"**{format_value(meth_val, 4)}**" if base_val and meth_val and meth_val > base_val else format_value(meth_val, 4)
        md.append(f"| {scene} | {format_value(base_val, 4)} | {meth_str} | {delta} |")
    md.append("")
    
    # === LPIPS Table ===
    md.append("## LPIPS ↓ Càng thấp càng tốt")
    md.append("")
    md.append(f"| Dataset | {baseline_name} | {method_name} | Δ |")
    md.append("|---------|------------|------------------|---|")
    
    for scene in all_scenes:
        base_val = baseline_metrics.get(scene, {}).get("lpips")
        meth_val = method_metrics.get(scene, {}).get("lpips")
        delta = ""
        if base_val and meth_val:
            diff = meth_val - base_val
            emoji = " ✅" if diff < 0 else (" ⚠️" if diff > 0.01 else "")
            delta = f"{diff:+.4f}{emoji}"
        meth_str = f"**{format_value(meth_val, 4)}**" if base_val and meth_val and meth_val < base_val else format_value(meth_val, 4)
        md.append(f"| {scene} | {format_value(base_val, 4)} | {meth_str} | {delta} |")
    md.append("")
    
    # === ATE RMSE Table ===
    md.append("## ATE RMSE (m) ↓ Càng thấp càng tốt")
    md.append("")
    md.append(f"| Dataset | {baseline_name} | {method_name} | Δ |")
    md.append("|---------|------------|------------------|---|")
    
    for scene in all_scenes:
        base_val = baseline_metrics.get(scene, {}).get("ate_rmse")
        meth_val = method_metrics.get(scene, {}).get("ate_rmse")
        delta = ""
        if base_val and meth_val:
            diff = meth_val - base_val
            emoji = " ✅" if diff < 0 else (" ⚠️" if diff > 0.001 else "")
            delta = f"{diff:+.4f}{emoji}"
        meth_str = f"**{format_value(meth_val, 4)}**" if base_val and meth_val and meth_val < base_val else format_value(meth_val, 4)
        md.append(f"| {scene} | {format_value(base_val, 4)} | {meth_str} | {delta} |")
    md.append("")
    
    # === Gaussians Table ===
    md.append("## Số lượng Gaussians ↓ Càng ít càng tốt")
    md.append("")
    md.append(f"| Dataset | {baseline_name} | {method_name} | Δ |")
    md.append("|---------|------------|------------------|---|")
    
    for scene in all_scenes:
        base_gaus = baseline_metrics.get(scene, {}).get("gaussians")
        meth_gaus = method_metrics.get(scene, {}).get("gaussians")
        delta = ""
        if base_gaus and meth_gaus:
            diff = meth_gaus - base_gaus
            pct = (diff / base_gaus) * 100 if base_gaus > 0 else 0
            emoji = " ✅" if diff < 0 else ""
            delta = f"{diff:+,} ({pct:+.1f}%){emoji}"
        meth_str = f"**{meth_gaus:,}**" if base_gaus and meth_gaus and meth_gaus < base_gaus else (f"{meth_gaus:,}" if meth_gaus else "N/A")
        base_str = f"{base_gaus:,}" if base_gaus else "N/A"
        md.append(f"| {scene} | {base_str} | {meth_str} | {delta} |")
    md.append("")
    
    # === Tổng kết ===
    md.append("## Tổng kết")
    md.append("")
    
    def calc_avg(metrics, key):
        vals = [m.get(key) for m in metrics.values() if m.get(key)]
        return sum(vals) / len(vals) if vals else None
    
    metrics_summary = [
        ("PSNR", "psnr", "↑", lambda b, m: m - b),
        ("SSIM", "ssim", "↑", lambda b, m: m - b),
        ("LPIPS", "lpips", "↓", lambda b, m: m - b),
        ("ATE RMSE", "ate_rmse", "↓", lambda b, m: m - b),
        ("Gaussians", "gaussians", "↓", lambda b, m: m - b),
    ]
    
    for name, key, direction, diff_fn in metrics_summary:
        base_avg = calc_avg(baseline_metrics, key)
        meth_avg = calc_avg(method_metrics, key)
        if base_avg and meth_avg:
            diff = diff_fn(base_avg, meth_avg)
            better = (direction == "↑" and diff > 0) or (direction == "↓" and diff < 0)
            emoji = " ✅" if better else " ⚠️"
            if key == "gaussians":
                md.append(f"- **{name}**: {base_avg:,.0f} → {meth_avg:,.0f} (Δ = {diff:+,.0f}){emoji}")
            else:
                md.append(f"- **{name}**: {base_avg:.4f} → {meth_avg:.4f} (Δ = {diff:+.4f}){emoji}")
    
    md.append("")
    
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="So sánh kết quả Photo-SLAM")
    parser.add_argument("--baseline", "-b", default="results", help="Thư mục baseline")
    parser.add_argument("--method", "-m", default="results_cg", help="Thư mục method mới")
    parser.add_argument("--output", "-o", default=None, help="File output markdown")
    parser.add_argument("--iteration", "-i", type=int, default=0, help="Iteration (mặc định: 0)")
    parser.add_argument("--baseline-name", default="Photo-SLAM", help="Tên baseline")
    parser.add_argument("--method-name", default="Depth-Photo-SLAM", help="Tên method")
    
    args = parser.parse_args()
    
    print(f"Đọc baseline từ: {args.baseline}")
    baseline_metrics = get_scene_metrics(args.baseline, args.iteration)
    
    print(f"Đọc method từ: {args.method}")
    method_metrics = get_scene_metrics(args.method, args.iteration)
    
    if not baseline_metrics and not method_metrics:
        print("Không tìm thấy dữ liệu.")
        return
    
    md = generate_markdown(baseline_metrics, method_metrics, args.baseline_name, args.method_name)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(md)
        print(f"\nĐã lưu: {args.output}")
    else:
        print("")
        print(md)


if __name__ == "__main__":
    main()
