# Photo-SLAM PA Experiments - Quick Start Guide

Hướng dẫn nhanh để chạy toàn bộ pipeline: Build → Benchmark → Mesh → Eval

---

## 1. Kích hoạt môi trường

```bash
cd /media/tam/DATA/3D/CG-photo

# Thiết lập OpenCV library path (bắt buộc)
export LD_LIBRARY_PATH=/media/tam/DATA/3D/Photo-SLAM/third_party/opencv_install/lib:$LD_LIBRARY_PATH

# Kích hoạt Python environment cho mesh/eval
source scripts/tsdf_env/bin/activate
```

---

## 2. Build lại code (sau khi thay đổi)

### Build nhanh (chỉ file thay đổi):
```bash
cd build && make -j$(nproc)
```

### Build sạch (nếu có lỗi hoặc thay đổi CMakeLists.txt):
```bash
cd build
rm -rf *
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### Files thường thay đổi:
| File | Mô tả |
|------|-------|
| `src/gaussian_mapper.cpp` | Logic training và depth rendering |
| `include/gaussian_mapper.h` | Header definitions |
| `cuda_rasterizer/*.cu` | CUDA kernels |

---

## 3. Chạy Benchmark (Render Depth)

### Chạy PA6 (Best config: λ_geo=0.2):
```bash
./scripts/tum_rgbd_pa6.sh
```
> ⏱️ ~30-60 phút cho 3 datasets × 3 iterations

### Chạy các PA khác:
```bash
./scripts/tum_rgbd_pa5.sh  # λ_geo=1.0
./scripts/tum_rgbd_pa7.sh  # λ_geo=0.25
./scripts/tum_rgbd_pa9.sh  # λ_geo=0.15
```

### Output:
- Results: `results_pa6/tum_rgbd_*/rgbd_dataset_freiburg*/`
- Depth maps: `*_shutdown/depth/`
- Trajectory: `CameraTrajectory_TUM.txt`

---

## 4. Generate TSDF Meshes

### Từ Rendered Depth (Gaussian Splatting):
```bash
source scripts/tsdf_env/bin/activate
python3 scripts/generate_pa_meshes.py --pa PA6 --use_rendered_depth --verbose
```

### Từ Ground Truth Depth (Kinect sensor):
```bash
python3 scripts/generate_pa_meshes.py --pa PA6 --verbose
```

### Generate tất cả PA variants:
```bash
python3 scripts/generate_pa_meshes.py --all --verbose
```

### Output:
- Meshes: `meshes_pa/pa6/pa6_fr1_desk_run0_rendered.ply`
- GT Meshes: `meshes_pa/pa6/pa6_fr1_desk_run0_gt.ply`

---

## 5. Evaluate Meshes

### So sánh Rendered vs GT Depth:
```bash
source scripts/tsdf_env/bin/activate

python3 scripts/evaluate_meshes.py \
    --pred meshes_pa/pa6/pa6_fr1_desk_run0_rendered.ply \
    --gt meshes_pa/pa6/pa6_fr1_desk_run0_gt.ply \
    --output meshes_pa/pa6/eval_fr1_desk.json
```

### Evaluate tất cả 3 datasets:
```bash
for ds in fr1_desk fr2_xyz fr3_long; do
    python3 scripts/evaluate_meshes.py \
        --pred meshes_pa/pa6/pa6_${ds}_run0_rendered.ply \
        --gt meshes_pa/pa6/pa6_${ds}_run0_gt.ply \
        --output meshes_pa/pa6/eval_${ds}.json
done
```

---

## 6. One-liner: Full Pipeline

```bash
# 1. Build
cd /media/tam/DATA/3D/CG-photo && cd build && make -j$(nproc) && cd ..

# 2. Run PA6 benchmark (lâu)
./scripts/tum_rgbd_pa6.sh

# 3. Generate meshes
source scripts/tsdf_env/bin/activate
python3 scripts/generate_pa_meshes.py --pa PA6 --use_rendered_depth
python3 scripts/generate_pa_meshes.py --pa PA6

# 4. Evaluate
for ds in fr1_desk fr2_xyz fr3_long; do
    python3 scripts/evaluate_meshes.py \
        --pred meshes_pa/pa6/pa6_${ds}_run0_rendered.ply \
        --gt meshes_pa/pa6/pa6_${ds}_run0_gt.ply \
        --output meshes_pa/pa6/eval_${ds}.json
done
```

---

## Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| `libopencv_*.so: not found` | `export LD_LIBRARY_PATH=...` (xem bước 1) |
| `No module named 'open3d'` | `source scripts/tsdf_env/bin/activate` |
| Segfault khi chạy | Rebuild: `cd build && make clean && make -j$(nproc)` |
| `No frames integrated` | Kiểm tra association file và timestamp matching |

---

## Cấu trúc thư mục

```
CG-photo/
├── bin/                    # Executables
├── build/                  # Build directory
├── cfg/                    # Config files
├── results_pa6/            # Benchmark results
│   └── tum_rgbd_0/
│       └── rgbd_dataset_*/
│           └── *_shutdown/
│               ├── depth/  # Rendered depth maps
│               ├── image/  # Rendered images
│               └── ply/    # Point clouds
├── meshes_pa/              # Generated meshes
│   └── pa6/
│       ├── *_rendered.ply
│       └── *_gt.ply
└── scripts/
    ├── tum_rgbd_pa*.sh     # Benchmark scripts
    ├── generate_pa_meshes.py
    └── evaluate_meshes.py
```
