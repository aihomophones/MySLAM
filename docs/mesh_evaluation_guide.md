# Hướng dẫn Đánh giá Mesh PA6 trên Replica Dataset

Tài liệu này hướng dẫn quy trình đầy đủ để đánh giá geometry của Photo-SLAM PA6 trên Replica dataset.

## Tổng quan Pipeline

```
Photo-SLAM Results → Tạo Mesh → Cull Mesh → Đánh giá Metrics
```

---

## Bước 1: Tạo Mesh từ Photo-SLAM Results

### 1.1 Chuẩn bị

Đảm bảo bạn có:
- Photo-SLAM results tại `results_replica_pa6/replica_rgbd_0/{scene}/`
- Replica dataset tại `/media/tam/DATA/data/Replica/{scene}/`

### 1.2 Activate environment

```bash
source scripts/tsdf_env/bin/activate
```

### 1.3 Phương pháp 1: Dùng Photo-SLAM rendered depth + poses (KHUYẾN NGHỊ)

Sử dụng depth và poses hoàn toàn từ Photo-SLAM (không dùng GT):

```bash
python3 scripts/generate_mesh_from_photoslam.py \
    --result_dir results_replica_pa6/replica_rgbd_0/office0 \
    --output meshes/pa6_replica/office0.ply \
    --depth_scale 1000.0 \
    --voxel_size 0.01
```

**Lưu ý**: Chỉ có depth tại keyframes (~104 frames), không phải tất cả 2000 frames.

### 1.4 Phương pháp 2: Dùng GT depth + Photo-SLAM poses

Sử dụng depth từ Replica GT và poses từ Photo-SLAM:

```bash
python3 scripts/generate_replica_mesh_gpu.py \
    --result_dir results_replica_pa6/replica_rgbd_0/office0 \
    --dataset_path /media/tam/DATA/data/Replica/office0 \
    --output meshes/pa6_replica/office0.ply \
    --voxel_size 0.01 \
    --stride 1 \
    --cpu
```

### 1.5 Tham số quan trọng

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `--voxel_size` | 0.01 | Kích thước voxel (nhỏ hơn = chi tiết hơn) |
| `--sdf_trunc` | 0.04 | SDF truncation distance |
| `--depth_scale` | 1000.0 (Photo-SLAM) / 6553.5 (Replica GT) | Depth scale |
| `--stride` | 1 | Bỏ qua mỗi N frames |

---

## Bước 2: Cull Mesh (Loại bỏ vùng không nhìn thấy)

### 2.1 Tại sao cần cull?

- Loại bỏ các vùng nằm ngoài camera frustum
- Loại bỏ các vùng bị occlusion
- Đảm bảo so sánh công bằng với GT mesh

### 2.2 (Optional) Tạo Virtual Cameras TRƯỚC khi cull

Nếu muốn dùng virtual cameras (so sánh chuẩn với Co-SLAM):

```bash
cd neural_slam_eval-main

export XDG_SESSION_TYPE=x11
python create_virtual_cameras_replica.py \
    --config configs/Replica/office0.yaml \
    --data_dir /media/tam/DATA/data/Replica/office0
```

> **Lưu ý**: Cần GUI để chọn vị trí camera. Nhấn `.` để lưu từng camera view (5-10 views).

### 2.3 Cull PA6 Mesh

**Không dùng virtual cameras** (đơn giản hơn):

```bash
python cull_mesh.py \
    --config configs/Replica/office0.yaml \
    --input_mesh ../meshes/pa6_replica/office0.ply \
    --output_mesh ../meshes/pa6_replica/office0_culled.ply \
    --remove_occlusion \
    --gt_pose \
    --skip 2
```

**Có dùng virtual cameras** (sau khi đã tạo ở bước 2.2):

```bash
python cull_mesh.py \
    --config configs/Replica/office0.yaml \
    --input_mesh ../meshes/pa6_replica/office0.ply \
    --output_mesh ../meshes/pa6_replica/office0_culled.ply \
    --remove_occlusion \
    --virtual_cameras \
    --gt_pose \
    --skip 2
```

---

## Bước 3: Đánh giá Metrics

### 3.1 3D Metrics (Accuracy, Completion, Completion Ratio)

```bash
python eval_recon.py \
    --rec_mesh ../meshes/pa6_replica/office0_culled.ply \
    --gt_mesh /media/tam/DATA/data/Replica/office0_mesh_triangles.ply \
    -3d
```

**Output mẫu:**
```
accuracy:  1.85
completion:  2.10
completion ratio:  94.5
```

### 3.2 2D Metrics (Depth L1)

```bash
python eval_recon.py \
    --rec_mesh ../meshes/pa6_replica/office0_culled.ply \
    --gt_mesh /media/tam/DATA/data/Replica/office0_mesh_triangles.ply \
    --dataset_type Replica \
    -2d
```

### 3.3 Giải thích Metrics

| Metric | Đơn vị | Ý nghĩa | Tốt hơn |
|--------|--------|---------|---------|
| **Accuracy** | cm | Khoảng cách trung bình từ reconstructed → GT | ↓ thấp hơn |
| **Completion** | cm | Khoảng cách trung bình từ GT → reconstructed | ↓ thấp hơn |
| **Comp Ratio** | % | % điểm GT nằm trong 5cm của reconstructed | ↑ cao hơn |
| **Depth L1** | cm | L1 error giữa rendered depth maps | ↓ thấp hơn |

---

## Script tự động cho tất cả scenes

```bash
#!/bin/bash
SCENES="room0 room1 room2 office0 office1 office2 office3 office4"
RESULT_DIR="results_replica_pa6/replica_rgbd_0"
DATASET_DIR="/media/tam/DATA/data/Replica"
OUTPUT_DIR="meshes/pa6_replica"

source scripts/tsdf_env/bin/activate

for scene in $SCENES; do
    echo "Processing $scene..."
    
    # 1. Generate mesh từ Photo-SLAM outputs
    python3 scripts/generate_mesh_from_photoslam.py \
        --result_dir $RESULT_DIR/$scene \
        --output $OUTPUT_DIR/${scene}.ply \
        --depth_scale 1000.0
    
    # 2. Cull mesh
    cd neural_slam_eval-main
    python cull_mesh.py \
        --config configs/Replica/${scene}.yaml \
        --input_mesh ../$OUTPUT_DIR/${scene}.ply \
        --output_mesh ../$OUTPUT_DIR/${scene}_culled.ply \
        --remove_occlusion --gt_pose --skip 2
    
    # 3. Evaluate
    python eval_recon.py \
        --rec_mesh ../$OUTPUT_DIR/${scene}_culled.ply \
        --gt_mesh $DATASET_DIR/${scene}_mesh_triangles.ply \
        -3d
    
    cd ..
done
```

---

## Benchmark Reference (từ các phương pháp khác)

| Method | Acc↓ | Comp↓ | Comp%↑ | Depth L1↓ |
|--------|------|-------|--------|-----------|
| iMAP | 3.62 | 4.93 | 80.51 | 4.64 |
| NICE-SLAM | 2.37 | 2.64 | 91.13 | 1.90 |
| Co-SLAM | 2.10 | 2.08 | 93.44 | 1.51 |
| ESLAM | 2.18 | 1.75 | 96.46 | 0.94 |

---

## Troubleshooting

### Mesh bị lật ngược hoặc sai vị trí
→ Photo-SLAM trajectory bắt đầu từ identity, không align với Replica world coordinates

### Mesh rỗng hoặc quá ít vertices
→ Kiểm tra depth_scale (thử 1000.0 hoặc 6553.5)

### Culling loại bỏ quá nhiều
→ Giảm `--eps` hoặc tắt `--remove_occlusion`

### Config file lỗi đường dẫn
→ Sửa `datadir` trong `configs/Replica/{scene}.yaml` thành absolute path
