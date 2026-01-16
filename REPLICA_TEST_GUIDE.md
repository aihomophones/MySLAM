# Hướng dẫn Test và Đánh giá trên Dataset Replica

## Tổng quan

Đã tạo 3 file script để test và đánh giá Photo-SLAM trên dataset Replica:

### 1. **replica_rgbd_test.sh** - Simple RGB-D Testing
Script đơn giản nhất, chỉ chạy test RGB-D trên Replica dataset.

**Sử dụng:**
```bash
cd scripts
./replica_rgbd_test.sh
```

**Kết quả:**
- Chạy 5 iterations (0-4) trên 8 scenes Replica
- Lưu kết quả trong `results/replica_rgbd_0/`, `results/replica_rgbd_1/`, ...
- Không tự động evaluate

---

### 2. **replica_test_eval.sh** - Complete Test & Eval
Script đầy đủ với khả năng test cả RGB-D và Monocular, bao gồm evaluation.

**Sử dụng:**
```bash
cd scripts

# Chạy cả RGB-D và Monocular (mặc định)
./replica_test_eval.sh both

# Chỉ chạy RGB-D
./replica_test_eval.sh rgbd

# Chỉ chạy Monocular  
./replica_test_eval.sh mono
```

**Tính năng:**
- ✅ Tự động chạy training
- ✅ Tự động chạy evaluation (onekey.py)
- ✅ Hiển thị summary kết quả
- ✅ Hỗ trợ 3 modes: rgbd, mono, both
- ✅ Output có màu sắc dễ theo dõi

---

### 3. **run_replica_eval.sh** - Full Workflow
Script workflow đầy đủ với nhiều tùy chọn configuration.

**Sử dụng:**
```bash
cd scripts

# Mặc định: RGB-D, 5 iterations
./run_replica_eval.sh

# Custom options
./run_replica_eval.sh -m rgbd -i 10 -r replica_experiment1
./run_replica_eval.sh -m mono -i 3 -r replica_mono_test
```

**Tham số:**
- `-m <mode>`: rgbd hoặc mono
- `-i <iterations>`: Số lần chạy (mặc định: 5)
- `-r <result_dir>`: Tên thư mục kết quả

**Workflow:**
1. 📊 Chạy training trên tất cả scenes
2. 📈 Evaluate với onekey.py
3. 📋 Tạo summary report

---

## Cấu trúc Dataset

Script yêu cầu dataset Replica ở:
```
/media/tam/DATA/data/Replica/
├── office0/
├── office1/
├── office2/
├── office3/
├── office4/
├── room0/
├── room1/
└── room2/
```

## Scenes được Test

8 scenes Replica:
- **Offices:** office0, office1, office2, office3, office4
- **Rooms:** room0, room1, room2

## Kết quả Output

### Thư mục kết quả:
```
results/
├── replica_rgbd_0/
│   ├── office0/
│   ├── office1/
│   └── ...
├── replica_rgbd_1/
├── replica_mono_0/
├── log.txt          # Text summary
└── log.csv          # CSV format
```

### Log format:
Mỗi scene sẽ có metrics:
- **ATE (T)**: Absolute Trajectory Error - Translation
- **R**: Rotation error  
- **PSNR**: Peak Signal-to-Noise Ratio
- **SSIM**: Structural Similarity Index
- **LPIPS**: Learned Perceptual Image Patch Similarity
- **Tracking FPS**
- **Rendering FPS**
- **T_std**: Standard deviation of translation error

## Quy trình Đề xuất

### Test nhanh (RGB-D only):
```bash
cd scripts
./replica_rgbd_test.sh
cd ../Photo-SLAM-eval
python onekey.py -d /media/tam/DATA/data -r ../results/
cd ..
```

### Test đầy đủ (RGB-D + Mono):
```bash
cd scripts
./replica_test_eval.sh both
# Tự động chạy hết, chờ kết quả
```

### Test có customize:
```bash
cd scripts
./run_replica_eval.sh -m rgbd -i 10 -r replica_pa10
```

## Config Files

Scripts sử dụng các config files:
- **ORB-SLAM3 configs:** `cfg/ORB_SLAM3/RGB-D/Replica/*.yaml`
- **ORB-SLAM3 configs:** `cfg/ORB_SLAM3/Monocular/Replica/*.yaml`
- **Gaussian Mapper configs:** `cfg/gaussian_mapper/RGB-D/Replica/replica_rgbd.yaml`
- **Gaussian Mapper configs:** `cfg/gaussian_mapper/Monocular/Replica/replica_mono.yaml`

## Executables

Scripts gọi các binary:
- `bin/replica_rgbd` - RGB-D mode
- `bin/replica_mono` - Monocular mode

## Lưu ý

1. **Build trước khi chạy:**
   ```bash
   cd build
   make -j$(nproc)
   cd ..
   ```

2. **Kiểm tra dataset path:**
   Nếu dataset không ở `/media/tam/DATA/data`, sửa biến `DATASET_PATH` trong script

3. **Thời gian chạy:**
   - Mỗi scene: ~5-15 phút (tùy GPU)
   - 8 scenes x 5 iterations ≈ 5-12 giờ cho full test

4. **Disk space:**
   Mỗi iteration cần ~5-10GB cho tất cả scenes

## Troubleshooting

### Script không chạy được:
```bash
chmod +x replica_test_eval.sh replica_rgbd_test.sh run_replica_eval.sh
```

### Dataset không tìm thấy:
Kiểm tra path và sửa trong script:
```bash
DATASET_PATH="/media/tam/DATA/data"
```

### Evaluation failed:
Kiểm tra Python environment và dependencies:
```bash
cd Photo-SLAM-eval
pip install -r requirements.txt
```

## So sánh với TUM Scripts

Scripts Replica tương tự TUM scripts nhưng:
- ✅ Không cần association files
- ✅ Đơn giản hơn (8 scenes vs 3 scenes)
- ✅ Ground truth có sẵn trong dataset
- ✅ Phù hợp cho indoor scene evaluation
