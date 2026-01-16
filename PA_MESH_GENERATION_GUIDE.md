# 📐 TSDF Mesh Generation cho PA Experiments

Hướng dẫn tạo meshes từ estimated trajectories của các phương án PA1-PA10.

## 🎯 Mục đích

Tạo dense 3D meshes từ estimated camera poses của Photo-SLAM để:
1. **Đánh giá geometric accuracy**: So sánh với ground truth TSDF meshes
2. **Visualize reconstruction quality**: Xem chất lượng tái dựng 3D
3. **Mesh metrics**: Tính accuracy, completeness, F-score

## 📁 Output Structure

```
meshes_pa/
├── pa1/
│   ├── pa1_fr1_desk_run0.ply
│   ├── pa1_fr2_xyz_run0.ply
│   └── pa1_fr3_long_run0.ply
├── pa6/          # BEST variant ⭐
│   ├── pa6_fr1_desk_run0.ply
│   ├── pa6_fr2_xyz_run0.ply
│   └── pa6_fr3_long_run0.ply
└── ... (PA3-PA10)
```

## 🚀 Cách sử dụng

### 1. Batch Script (Đơn giản nhất) ⭐

```bash
cd scripts

# Tạo meshes cho TẤT CẢ PA (chất lượng standard)
./generate_pa_meshes_batch.sh

# Tạo meshes chất lượng CAO (5mm voxels, chậm hơn)
./generate_pa_meshes_batch.sh --high-quality

# Tạo meshes chỉ cho PA6 (best variant)
./generate_pa_meshes_batch.sh --pa PA6

# Tạo meshes chất lượng cao cho PA6
./generate_pa_meshes_batch.sh --high-quality --pa PA6

# Tạo meshes cho nhiều PA cụ thể
./generate_pa_meshes_batch.sh --pa PA6
./generate_pa_meshes_batch.sh --pa PA7
./generate_pa_meshes_batch.sh --pa PA8
```

### 2. Python Script (Chi tiết hơn)

```bash
cd scripts
source tsdf_env/bin/activate

# Tạo meshes cho tất cả PA
python generate_pa_meshes.py --all

# Tạo meshes cho PA cụ thể
python generate_pa_meshes.py --pa PA6 PA7 PA8

# Chất lượng cao (5mm voxels)
python generate_pa_meshes.py --all --voxel_size 0.005 --sdf_trunc 0.02

# Sử dụng run index khác (mặc định là 0)
python generate_pa_meshes.py --all --run_index 1

# Custom paths
python generate_pa_meshes.py --all \
    --data_path /path/to/TUM \
    --results_base /path/to/CG-photo \
    --output_dir /path/to/output

# Verbose logging
python generate_pa_meshes.py --all --verbose
```

## ⚙️ Cấu hình Quality

### Standard Quality (Mặc định)
- **Voxel size**: 0.01m (1cm)
- **SDF truncation**: 0.04m
- **Stride**: 1 (mọi frame)
- **Thời gian**: ~5-10 phút/mesh
- **Disk space**: ~50-200 MB/mesh

### High Quality
- **Voxel size**: 0.005m (5mm)
- **SDF truncation**: 0.02m
- **Stride**: 1 (mọi frame)
- **Thời gian**: ~15-30 phút/mesh
- **Disk space**: ~200-600 MB/mesh

### Low Quality (Faster)
- **Voxel size**: 0.02m (2cm)
- **SDF truncation**: 0.08m
- **Stride**: 2 (mỗi frame thứ 2)
- **Thời gian**: ~2-5 phút/mesh
- **Disk space**: ~20-80 MB/mesh

## 📊 Ví dụ sử dụng cụ thể

### Case 1: Đánh giá nhanh PA6 (Best)
```bash
# Tạo meshes standard quality cho PA6
./generate_pa_meshes_batch.sh --pa PA6

# Output:
# meshes_pa/pa6/pa6_fr1_desk_run0.ply
# meshes_pa/pa6/pa6_fr2_xyz_run0.ply
# meshes_pa/pa6/pa6_fr3_long_run0.ply
```

### Case 2: So sánh tất cả PA variants
```bash
# Tạo meshes cho tất cả PA (có thể chạy qua đêm)
./generate_pa_meshes_batch.sh

# Sẽ tạo 30 meshes (10 PA × 3 datasets)
# Thời gian: ~2-3 giờ (standard quality)
```

### Case 3: High quality cho PA6 để submit paper
```bash
# Tạo high quality meshes cho PA6
./generate_pa_meshes_batch.sh --high-quality --pa PA6

# Output: High resolution meshes (5mm voxels)
```

### Case 4: So sánh lambda_geo variants (PA5-PA10)
```bash
# Tạo meshes cho các PA dùng L_sensor với lambda khác nhau
for pa in PA5 PA6 PA7 PA9 PA10; do
    ./generate_pa_meshes_batch.sh --pa $pa
done
```

## 🔍 Xem và phân tích meshes

### Visualize mesh
```bash
cd scripts
source tsdf_env/bin/activate

# Xem mesh
python view_mesh.py ../meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

### Analyze mesh statistics
```bash
# Phân tích mesh (vertices, triangles, bounds, etc.)
python analyze_mesh.py ../meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

### So sánh với ground truth
```bash
# Compare PA6 mesh với ground truth TSDF
python evaluate_meshes.py \
    --gt ../meshes/freiburg1_desk_dense.ply \
    --pred ../meshes_pa/pa6/pa6_fr1_desk_run0.ply
```

## 📝 Cấu trúc input/output

### Input (từ PA results)
```
results_pa6/
└── tum_rgbd_0/
    ├── rgbd_dataset_freiburg1_desk/
    │   └── CameraTrajectory_TUM.txt    # ← Estimated poses
    ├── rgbd_dataset_freiburg2_xyz/
    │   └── CameraTrajectory_TUM.txt
    └── rgbd_dataset_freiburg3_long_office_household/
        └── CameraTrajectory_TUM.txt
```

### Input (từ TUM dataset)
```
/media/tam/DATA/data/TUM/
├── rgbd_dataset_freiburg1_desk/
│   ├── rgb/              # RGB images
│   ├── depth/            # Depth images
│   └── associations.txt  # RGB-Depth associations
├── rgbd_dataset_freiburg2_xyz/
└── rgbd_dataset_freiburg3_long_office_household/
```

### Output
```
meshes_pa/
├── pa6/
│   ├── pa6_fr1_desk_run0.ply    # 3D mesh file
│   ├── pa6_fr2_xyz_run0.ply
│   └── pa6_fr3_long_run0.ply
└── README.md
```

## 🛠️ Troubleshooting

### Error: "Trajectory file not found"
```bash
# Kiểm tra PA results có tồn tại không
ls -la results_pa6/tum_rgbd_0/*/CameraTrajectory_TUM.txt

# Đảm bảo đã chạy PA6 experiment
./scripts/run_pa6.sh
```

### Error: "Association file not found"
```bash
# Tạo associations.txt cho TUM dataset
cd /media/tam/DATA/data/TUM/rgbd_dataset_freiburg1_desk
python /media/tam/DATA/3D/CG-photo/scripts/associate.py \
    rgb.txt depth.txt > associations.txt
```

### Error: "No poses loaded"
```bash
# Kiểm tra file trajectory
head results_pa6/tum_rgbd_0/rgbd_dataset_freiburg1_desk/CameraTrajectory_TUM.txt

# File phải có format: timestamp tx ty tz qx qy qz qw
```

### Warning: "No frames were integrated"
- Kiểm tra timestamp matching giữa poses và RGB-D pairs
- Thử tăng `max_diff` parameter trong code
- Kiểm tra RGB/depth images có tồn tại không

## 💡 Tips

### 1. Chạy parallel để nhanh hơn
```bash
# Chạy 3 PA song song (nếu có đủ RAM)
./generate_pa_meshes_batch.sh --pa PA6 &
./generate_pa_meshes_batch.sh --pa PA7 &
./generate_pa_meshes_batch.sh --pa PA8 &
wait
```

### 2. Optimize disk space
```bash
# Dùng low quality cho testing nhanh
./generate_pa_meshes_batch.sh --low-quality --pa PA6

# Sau đó tạo high quality cho PA tốt nhất
./generate_pa_meshes_batch.sh --high-quality --pa PA6
```

### 3. Xem progress
```bash
# Chạy với verbose để thấy chi tiết
python generate_pa_meshes.py --pa PA6 --verbose

# Hoặc monitor file size
watch -n 5 'du -sh meshes_pa/*/*'
```

## 📊 Expected Output

### Successful run
```
========================================
Photo-SLAM PA Mesh Generation Batch
========================================

Configuration:
  Quality: standard
  Voxel size: 0.01m
  SDF truncation: 0.04m
  Stride: 1
  Run index: 0

============================================================
Processing PA6: L_sensor λ=0.2 ⭐BEST
============================================================

Creating mesh: PA6 - rgbd_dataset_freiburg1_desk
============================================================
Reading trajectory from: .../CameraTrajectory_TUM.txt
Loaded 572 estimated poses
...
Integration summary:
  Total frames: 573
  Integrated: 572
  Skipped (no pose): 1
  Skipped (no file): 0

Extracting triangle mesh...
Mesh statistics:
  Vertices: 245,123
  Triangles: 487,456
File size: 52.3 MB

✅ Success!
```

## 📚 Tài liệu liên quan

- **Ground truth meshes**: `meshes/README.md`
- **TSDF mesh script**: `scripts/tsdf_mesh_from_tum.py`
- **PA experiments summary**: `PA_EXPERIMENTS_SUMMARY.md`
- **Results evaluation**: `Photo-SLAM-eval/onekey.py`

---

*Created: 2026-01-15*  
*Script: `scripts/generate_pa_meshes.py`*  
*Batch: `scripts/generate_pa_meshes_batch.sh`*
