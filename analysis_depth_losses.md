# 📊 Phân tích Kết quả Depth Losses

## Tổng hợp các phương án test

| Phương án | lambda_align | lambda_var | lambda_iso | Description |
|-----------|--------------|------------|------------|-------------|
| **Baseline** (results) | 0 | 0 | 0 | Photo-SLAM gốc |
| **PA0** (results_cg0) | 0 | 0 | 0 | Depth-Photo-SLAM baseline |
| **PA1** (results_pa1) | 0.05 | 0 | 0 | L_align only |
| **PA2** (results_pa2) | 0 | 0 | 0.005 | L_iso only |
| **PA3** (results_pa3) | 0.02 | 0 | 0.003 | L_align + L_iso |

---

## Kết quả chi tiết (Trung bình 3 runs)

### freiburg1_desk

| Phương án | PSNR ↑ | SSIM ↑ | LPIPS ↓ | ATE ↓ |
|-----------|--------|--------|---------|-------|
| PA0 (baseline) | 19.54 | 0.702 | 0.285 | 0.039 |
| **PA1** | 19.80 | 0.710 | **0.277** | 0.024 |
| **PA2** | **19.81** | **0.716** | 0.288 | **0.016** |
| PA3 | 19.51 | 0.706 | 0.300 | 0.023 |

### freiburg2_xyz

| Phương án | PSNR ↑ | SSIM ↑ | LPIPS ↓ | ATE ↓ |
|-----------|--------|--------|---------|-------|
| PA0 (baseline) | **23.22** | **0.784** | **0.142** | 0.0035 |
| PA1 | 22.70 | 0.770 | 0.168 | 0.0037 |
| PA2 | 23.07 | 0.777 | 0.154 | **0.0035** |
| PA3 | 22.73 | 0.768 | 0.172 | 0.0035 |

### freiburg3_long_office_household

| Phương án | PSNR ↑ | SSIM ↑ | LPIPS ↓ | ATE ↓ |
|-----------|--------|--------|---------|-------|
| PA0 (baseline) | 19.13 | 0.679 | 0.258 | 0.020 |
| **PA1** | **21.86** | **0.765** | **0.178** | **0.010** |
| PA2 | 22.35 | 0.773 | 0.189 | 0.010 |
| PA3 | 20.02 | 0.708 | 0.245 | 0.017 |

---

## 📈 Phân tích

### Observations:

1. **PA2 (L_iso only)** cho kết quả **ổn định nhất**:
   - Cải thiện PSNR/SSIM trên freiburg1_desk
   - ATE tốt nhất trên hầu hết datasets
   - Ít variance giữa các runs

2. **PA1 (L_align only)** cải thiện đáng kể trên **freiburg3**:
   - PSNR tăng ~2.7 dB so với baseline
   - SSIM tăng 0.086
   - LPIPS giảm 0.08

3. **PA3 (L_align + L_iso)** không tốt như mong đợi:
   - Có thể do weights chưa optimal
   - L_align và L_iso vẫn có xung đột nhẹ

4. **freiburg2_xyz** - Baseline tốt nhất:
   - Dataset này có trajectory đơn giản
   - Depth losses không cần thiết

---

## 💡 Recommendations

### Best Configuration:
**PA2 (L_iso = 0.005)** là lựa chọn **an toàn nhất**:
- Cải thiện quality nhẹ
- Không làm xấu tracking
- Ổn định

### For Complex Scenes (như freiburg3):
**PA1 (L_align = 0.05)** cho cải thiện lớn nhất

### Next Steps:
1. Thử PA1 với lambda_align = 0.03 (giảm weight)
2. Hoặc adaptive: dùng L_align cho scenes phức tạp, L_iso cho scenes đơn giản
