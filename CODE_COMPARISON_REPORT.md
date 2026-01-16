# So sánh Code: Photo-SLAM PA6 vs CG-SLAM Diff-Gaussian-Rasterization

**Ngày cập nhật:** 2026-01-16  
**Mục đích:** So sánh chi tiết logic backward pass giữa PA6 (Photo-SLAM) và CG-SLAM để đánh giá mức độ hoàn thiện của depth gradient implementation

---

## 📋 Tổng quan

| Thành phần | PA6 (`cuda_rasterizer/`) | CG-SLAM (`diff-gaussian-rasterization-light/`) |
|------------|--------------------------|------------------------------------------------|
| **Backward file** | `backward.cu` + `backward_depth.cuh` (238 lines) | `backward.cu` (909 lines) |
| **Depth gradient** | ✅ Có đầy đủ | ✅ Có đầy đủ + thêm features |
| **Gradient → mean3D** | ✅ Có | ✅ Có |
| **Variance gradient** | ❌ Không | ✅ Có |
| **Median depth gradient** | ❌ Không ở render | ✅ Có trong render kernel |
| **Camera pose gradient** | ❌ Không | ✅ Có |
| **gt_depth trong backward** | ❌ Không | ✅ Có |

---

## 🔍 So sánh Chi tiết Backward Pass

### 1. Render Backward Kernel

#### 1.1 Kernel Signature

**PA6** (`backward_depth.cuh` line 8-27):
```cpp
template <uint32_t C>
__global__ void renderCUDAWithDepth(
    const uint2* __restrict__ ranges,
    const uint32_t* __restrict__ point_list,
    int W, int H,
    const float* __restrict__ bg_color,
    const float2* __restrict__ points_xy_image,
    const float4* __restrict__ conic_opacity,
    const float* __restrict__ colors,
    const float* __restrict__ depths,
    const float* __restrict__ final_Ts,
    const uint32_t* __restrict__ n_contrib,
    const float* __restrict__ dL_dpixels,
    const float* __restrict__ dL_ddepth,        // ✅ Depth gradient input
    const float* __restrict__ dL_ddepth_sq,     // ✅ Depth² gradient input
    float3* __restrict__ dL_dmean2D,
    float4* __restrict__ dL_dconic2D,
    float* __restrict__ dL_dopacity,
    float* __restrict__ dL_dcolors,
    float* __restrict__ dL_ddepths)             // ✅ Output: per-Gaussian depth grad
```

**CG-SLAM** (`backward.cu` line 419-450):
```cpp
template <uint32_t C>
__global__ void renderCUDA(
    // ... basic params ...
    const float* __restrict__ depths,
    const float* __restrict__ alphas,
    const uint32_t* __restrict__ n_contrib,
    const float* __restrict__ dL_dpixels,
    const float* __restrict__ dL_dpixel_depths,       // ✅ Depth gradient
    const float* __restrict__ dL_dpixel_median_depths, // ✅ THÊM: Median depth grad
    const float* __restrict__ dL_dpixel_depth_vars,   // ✅ THÊM: Variance grad
    float3* __restrict__ dL_dmean2D,
    float4* __restrict__ dL_dconic2D,
    float* __restrict__ dL_dopacity,
    float* __restrict__ dL_dcolors,
    float* __restrict__ dL_ddepths,
    float2* dgndcs_dview,                       // ✅ THÊM: Pose gradient
    float* __restrict__ dL_dview,               // ✅ THÊM: Pose gradient
    float* dg_camd_dviewmatrix,                 // ✅ THÊM: Pose chain rule
    const float3* means,                        // ✅ THÊM: For median depth grad
    const float* view,                          // ✅ THÊM: View matrix
    glm::vec3* dL_dmeans,                       // ✅ THÊM: Direct mean grad output
    const float* __restrict__ gt_depth,         // ✅ THÊM: GT depth for variance
    bool track_off,                             // ✅ THÊM: Flag
    bool map_off)                               // ✅ THÊM: Flag
```

---

#### 1.2 Depth Gradient to Per-Gaussian

**PA6** (`backward_depth.cuh` line 121-124):
```cpp
// Depth gradient: dL/d_depth_i = dL/dD * weight
if (dL_ddepths != nullptr) {
    atomicAdd(&(dL_ddepths[global_id]), weight * dL_dpixel_depth);
}
```

**CG-SLAM** (`backward.cu` line 609-612):
```cpp
if(!map_off)
{
    atomicAdd(&(dL_ddepths[global_id]), 
              dL_ddepth + dL_dpixel_depth_var * dpixel_depth_ddepth * 2. * (c_d - gt_px_depth));
}
```

**📊 So sánh:**
| Aspect | PA6 | CG-SLAM |
|--------|-----|---------|
| Basic depth grad | ✅ `weight * dL_dpixel_depth` | ✅ `dL_ddepth` |
| Variance term | ❌ Không | ✅ `dL_dpixel_depth_var * 2 * (c_d - gt_px_depth)` |
| GT depth usage | ❌ Không | ✅ Có |
| map_off flag | ❌ Không | ✅ Có |

---

#### 1.3 Depth Contribution to Alpha Gradient

**PA6** (`backward_depth.cuh` line 126-129):
```cpp
// Depth contribution to alpha gradient
accum_depth_rec = last_alpha * last_depth + (1.f - last_alpha) * accum_depth_rec;
last_depth = gaussian_depth;
dL_dalpha += (gaussian_depth - accum_depth_rec) * dL_dpixel_depth * T;
```

**CG-SLAM** (`backward.cu` line 600-608):
```cpp
const float c_d = collected_depths[j];
const float c_var = (c_d - gt_px_depth) * (c_d - gt_px_depth);  // ✅ Variance with GT
accum_depth_rec = last_alpha * last_depth + (1.f - last_alpha) * accum_depth_rec;
last_depth = c_d;
accum_var_rec = last_alpha * last_var + (1.f - last_alpha) * accum_var_rec;
last_var = c_var;

dL_dalpha += (c_d - accum_depth_rec) * dL_dpixel_depth;
dL_dalpha += (c_var - accum_var_rec) * dL_dpixel_depth_var;  // ✅ Variance contribution
```

**📊 So sánh:**
- PA6: Depth contribution ✅ (tương tự CG-SLAM)
- CG-SLAM: Thêm **variance contribution** dựa trên GT depth

---

### 2. Preprocess Backward (Depth → 3D Mean)

#### 2.1 PA6 Implementation

**PA6** (`backward_depth.cuh` line 198-206):
```cpp
// Depth gradient: depth = viewmatrix[2]*x + viewmatrix[6]*y + viewmatrix[10]*z
if (dL_ddepths != nullptr) {
    float dL_ddepth = dL_ddepths[idx];
    dL_dmean.x += dL_ddepth * viewmatrix[2];
    dL_dmean.y += dL_ddepth * viewmatrix[6];
    dL_dmean.z += dL_ddepth * viewmatrix[10];
}

dL_dmeans[idx] += dL_dmean;
```

#### 2.2 CG-SLAM Implementation

**CG-SLAM** (`backward.cu` line 398-407):
```cpp
// Compute loss gradient w.r.t. 3D means due to gradients of depth
glm::vec3 dL_dmean2;
float mul3 = view[2] * m.x + view[6] * m.y + view[10] * m.z + view[14];
dL_dmean2.x = (view[2] - view[3] * mul3) * dL_ddepth[idx];
dL_dmean2.y = (view[6] - view[7] * mul3) * dL_ddepth[idx];
dL_dmean2.z = (view[10] - view[11] * mul3) * dL_ddepth[idx];

// That's the third part of the mean gradient.
dL_dmeans[idx] += dL_dmean2;
```

**📊 So sánh:**

| Aspect | PA6 | CG-SLAM |
|--------|-----|---------|
| Basic gradient | `viewmatrix[2,6,10] * dL_ddepth` | `(view[i] - view[3/7/11] * mul3) * dL_ddepth` |
| Perspective correction | ❌ Không có `mul3` term | ✅ Có perspective correction |
| Formula | **Approximate** (assumes orthographic) | **Exact** (full chain rule) |

> **⚠️ QUAN TRỌNG:** PA6 thiếu perspective correction term (`view[3/7/11] * mul3`), có thể gây ra gradient không chính xác cho các object ở độ sâu khác nhau.

---

### 3. Median Depth Gradient

**PA6:** ❌ **KHÔNG CÓ** gradient cho median depth trong render kernel

**CG-SLAM** (`backward.cu` line 656-664):
```cpp
if (T > 0.5f && mid_once)
{   
    float mul3 = view[2] * means[global_id].x + view[6] * means[global_id].y + 
                 view[10] * means[global_id].z + view[14];
    atomicAdd(&(dL_dmeans[global_id].x), (view[2] - view[3] * mul3) * dL_dpixel_median_depth);
    atomicAdd(&(dL_dmeans[global_id].y), (view[6] - view[7] * mul3) * dL_dpixel_median_depth);
    atomicAdd(&(dL_dmeans[global_id].z), (view[10] - view[11] * mul3) * dL_dpixel_median_depth);
    mid_once = false;
}
```

---

### 4. Camera Pose Gradient

**PA6:** ❌ **KHÔNG CÓ** - Photo-SLAM dùng ORB-SLAM cho tracking

**CG-SLAM** (`backward.cu` line 633-651):
```cpp
if (!track_off)
{
    float dL_dndcs_x = dL_dalpha * con_o.w * dG_ddelx * ddelx_dx;
    float dL_dndcs_y = dL_dalpha * con_o.w * dG_ddely * ddely_dy;

    dL_dv0 += dgndcs_dview[global_id * 12 + 0].x * dL_dndcs_x + ...;
    dL_dv2 += ... + dg_camd_dviewmatrix[global_id * 4 + 0] * dL_ddepth;
    // ... (tất cả 12 components của view matrix)
}
```

---

## 📊 Bảng Tổng Hợp

| Feature | PA6 | CG-SLAM | PA6 Status |
|---------|-----|---------|------------|
| **Render Backward** |
| Per-Gaussian depth gradient | ✅ | ✅ | ✅ Đầy đủ |
| Depth → alpha gradient | ✅ | ✅ | ✅ Đầy đủ |
| Variance → alpha gradient | ❌ | ✅ | ⚠️ Thiếu |
| Median depth gradient | ❌ | ✅ | ⚠️ Thiếu |
| **Preprocess Backward** |
| Depth → mean3D gradient | ✅ (simplified) | ✅ (full) | ⚠️ Thiếu perspective term |
| SH gradient | ✅ | ✅ | ✅ Đầy đủ |
| Cov3D gradient | ✅ | ✅ | ✅ Đầy đủ |
| **Camera Pose** |
| View matrix gradient | ❌ | ✅ | N/A (Photo-SLAM không cần) |
| **Interface** |
| gt_depth input | ❌ | ✅ | ⚠️ Không có |
| track_off/map_off flags | ❌ | ✅ | N/A |

---

## 🎯 Kết luận

### ✅ PA6 Làm Đúng (Core Functionality):
1. **Depth gradient cơ bản**: `dL_ddepths = weight * dL_dpixel_depth` ✅
2. **Depth → alpha gradient**: Đúng logic alpha-blending ✅
3. **Depth → mean3D gradient**: Có, nhưng simplified ⚠️
4. **Color/opacity gradient**: Hoàn toàn đúng ✅

### ⚠️ Khác biệt so với CG-SLAM:

1. **Thiếu Perspective Correction** (preprocess):
   - PA6: `dL_dmean.x += dL_ddepth * viewmatrix[2]`
   - CG-SLAM: `dL_dmean.x += (view[2] - view[3] * mul3) * dL_ddepth`
   - **Impact**: Gradient có thể không chính xác cho objects ở độ sâu khác nhau

2. **Thiếu Variance Gradient**:
   - PA6 không backprop gradient từ depth variance
   - **Impact**: Ít ảnh hưởng nếu không dùng variance loss

3. **Thiếu Median Depth Gradient trong Render**:
   - PA6: Median depth gradient được tính ở preprocess (nếu dùng median depth)
   - **Impact**: Có thể ảnh hưởng nếu dùng median depth loss

4. **Không có Camera Pose Gradient**:
   - **Impact**: Không ảnh hưởng vì Photo-SLAM dùng ORB-SLAM để tracking

### 📈 Đánh giá Tổng thể:

| Aspect | Rating | Comment |
|--------|--------|---------|
| **Core depth gradient** | 9/10 | Đầy đủ cho cơ bản |
| **Mathematical accuracy** | 7/10 | Thiếu perspective term |
| **Feature completeness** | 6/10 | Thiếu variance, median trong render |
| **Suitability for Photo-SLAM** | 8/10 | Đủ cho RGBD với GT depth |

---

## 🔧 Khuyến nghị Cải thiện

### Ngắn hạn (Không cần thay đổi):
- PA6 hiện tại **đủ functional** cho depth supervision cơ bản
- Gradient chảy đúng từ `L_geo` → `mean3D`

### Trung hạn (Optional):
1. Thêm perspective correction term vào `preprocessCUDAWithDepth`:
```cpp
float mul3 = viewmatrix[2] * m.x + viewmatrix[6] * m.y + viewmatrix[10] * m.z + viewmatrix[14];
dL_dmean.x += dL_ddepth * (viewmatrix[2] - viewmatrix[3] * mul3);
dL_dmean.y += dL_ddepth * (viewmatrix[6] - viewmatrix[7] * mul3);
dL_dmean.z += dL_ddepth * (viewmatrix[10] - viewmatrix[11] * mul3);
```

### Dài hạn (Major refactor):
- Full integration với CG-SLAM kernel nếu cần variance-based optimization

---

## 📁 Files So Sánh

| PA6 | CG-SLAM | So sánh |
|-----|---------|---------|
| `cuda_rasterizer/backward.cu` (661 lines) | `diff-gaussian-rasterization-light/cuda_rasterizer/backward.cu` (909 lines) | CG +248 lines |
| `cuda_rasterizer/backward_depth.cuh` (238 lines) | N/A (integrated) | PA6 modular |
| `cuda_rasterizer/backward.h` | `backward.h` | PA6 thêm depth functions |

---

*Report updated: 2026-01-16*
