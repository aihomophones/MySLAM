# Depth Rendering Implementation Guide

Bạn đã có depth rendering rồi! Chỉ cần thêm code save depth maps.

## ✅ Code Changes Needed

### 1. Modify Function Signature - `recordKeyframeRendered` 

**File**: `src/gaussian_mapper.cpp` (line 1768-1798)

Add depth parameter:

```cpp
void GaussianMapper::recordKeyframeRendered(
        torch::Tensor &rendered,
        torch::Tensor &ground_truth,
        torch::Tensor &rendered_depth,     // ← ADD THIS
        unsigned long kfid,
        std::filesystem::path result_img_dir,
        std::filesystem::path result_gt_dir,
        std::filesystem::path result_loss_dir,
        std::filesystem::path result_depth_dir,  // ← ADD THIS
        std::string name_suffix)
{
    // Existing RGB code...
    if (record_rendered_image_) {
        auto image_cv = tensor_utils::torchTensor2CvMat_Float32(rendered);
        cv::cvtColor(image_cv, image_cv, CV_RGB2BGR);
        image_cv.convertTo(image_cv, CV_8UC3, 255.0f);
        cv::imwrite(result_img_dir / (std::to_string(getIteration()) + "_" + std::to_string(kfid) + name_suffix + ".jpg"), image_cv);
    }

    // ... existing GT and loss code ...

    // ← ADD DEPTH SAVING CODE HERE
    if (record_rendered_image_) {  // Use same flag or create new one
        // Convert depth tensor to cv::Mat
        // Shape: [H, W] single channel
        auto depth_cv = tensor_utils::torchTensor2CvMat_Float32(rendered_depth.squeeze());
        
        // Option 1: Save as 16-bit PNG (lossless, compact)
        cv::Mat depth_16u;
        depth_cv.convertTo(depth_16u, CV_16U, 5000.0f);  // Scale: depth * 5000 (TUM format)
        cv::imwrite(result_depth_dir / (std::to_string(getIteration()) + "_" + std::to_string(kfid) + name_suffix + "_depth.png"), depth_16u);
        
        // Option 2: Save as float32 (for visualization)
        // Normalize depth to [0, 255] for visualization
        cv::Mat depth_vis;
        cv::normalize(depth_cv, depth_vis, 0, 255, cv::NORM_MINMAX);
        depth_vis.convertTo(depth_vis, CV_8U);
        cv::applyColorMap(depth_vis, depth_vis, cv::COLORMAP_JET);  // Color visualization
        cv::imwrite(result_depth_dir / (std::to_string(getIteration()) + "_" + std::to_string(kfid) + name_suffix + "_depth_vis.jpg"), depth_vis);
    }
}
```

### 2. Modify `renderAndRecordKeyframe`

**File**: `src/gaussian_mapper.cpp` (line 1852-1886)

Extract depth from render_pkg:

```cpp
void GaussianMapper::renderAndRecordKeyframe(
    std::shared_ptr<GaussianKeyframe> pkf,
    float &dssim,
    float &psnr,
    float &psnr_gs,
    double &render_time,
    std::filesystem::path result_img_dir,
    std::filesystem::path result_gt_dir,
    std::filesystem::path result_loss_dir,
    std::filesystem::path result_depth_dir,  // ← ADD THIS
    std::string name_suffix)
{
    auto start_timing = std::chrono::steady_clock::now();
    auto render_pkg = GaussianRenderer::render(
        pkf,
        pkf->image_height_,
        pkf->image_width_,
        gaussians_,
        pipe_params_,
        background_,
        override_color_
    );
    
    auto rendered_image = std::get<0>(render_pkg);
    // ← ADD DEPTH EXTRACTION
    auto rendered_depth = std::get<4>(render_pkg);  // Index 4 = depth
    
    torch::Tensor masked_image = rendered_image * undistort_mask_[pkf->camera_id_];
    torch::cuda::synchronize();
    auto end_timing = std::chrono::steady_clock::now();
    auto render_time_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_timing - start_timing).count();
    render_time = 1e-6 * render_time_ns;
    auto gt_image = pkf->original_image_;

    dssim = loss_utils::ssim(masked_image, gt_image, device_type_).item().toFloat();
    psnr = loss_utils::psnr(masked_image, gt_image).item().toFloat();
    psnr_gs = loss_utils::psnr_gaussian_splatting(masked_image, gt_image).item().toFloat();

    // ← UPDATE CALL
    recordKeyframeRendered(
        masked_image, 
        gt_image, 
        rendered_depth,  // ← ADD THIS
        pkf->fid_, 
        result_img_dir, 
        result_gt_dir, 
        result_loss_dir, 
        result_depth_dir,  // ← ADD THIS
        name_suffix
    );    
}
```

### 3. Modify `renderAndRecordAllKeyframes`

**File**: `src/gaussian_mapper.cpp` (line 1888-1937)

Create depth directory:

```cpp
void GaussianMapper::renderAndRecordAllKeyframes(
    std::string name_suffix)
{
    std::filesystem::path result_dir = result_dir_ / (std::to_string(getIteration()) + name_suffix);
    CHECK_DIRECTORY_AND_CREATE_IF_NOT_EXISTS(result_dir)

    std::filesystem::path image_dir = result_dir / "image";
    if (record_rendered_image_)
        CHECK_DIRECTORY_AND_CREATE_IF_NOT_EXISTS(image_dir);

    std::filesystem::path image_gt_dir = result_dir / "image_gt";
    if (record_ground_truth_image_)
        CHECK_DIRECTORY_AND_CREATE_IF_NOT_EXISTS(image_gt_dir);

    std::filesystem::path image_loss_dir = result_dir / "image_loss";
    if (record_loss_image_) {
        CHECK_DIRECTORY_AND_CREATE_IF_NOT_EXISTS(image_loss_dir);
    }

    // ← ADD DEPTH DIRECTORY
    std::filesystem::path depth_dir = result_dir / "depth";
    if (record_rendered_image_)  // Or create new flag: record_depth_
        CHECK_DIRECTORY_AND_CREATE_IF_NOT_EXISTS(depth_dir);

    // ... existing file streams ...

    std::size_t nkfs = scene_->keyframes().size();
    auto kfit = scene_->keyframes().begin();
    float dssim, psnr, psnr_gs;
    double render_time;
    for (std::size_t i = 0; i < nkfs; ++i) {
        // ← UPDATE CALL
        renderAndRecordKeyframe(
            (*kfit).second, 
            dssim, 
            psnr, 
            psnr_gs, 
            render_time, 
            image_dir, 
            image_gt_dir, 
            image_loss_dir,
            depth_dir,  // ← ADD THIS
            ""
        );
        
        // ... existing output code ...
        ++kfit;
    }
}
```

### 4. Update Header File

**File**: `include/gaussian_mapper.h`

Update function signatures:

```cpp
void recordKeyframeRendered(
    torch::Tensor &rendered,
    torch::Tensor &ground_truth,
    torch::Tensor &rendered_depth,  // ← ADD
    unsigned long kfid,
    std::filesystem::path result_img_dir,
    std::filesystem::path result_gt_dir,
    std::filesystem::path result_loss_dir,
    std::filesystem::path result_depth_dir,  // ← ADD
    std::string name_suffix = "");

void renderAndRecordKeyframe(
    std::shared_ptr<GaussianKeyframe> pkf,
    float &dssim,
    float &psnr,
    float &psnr_gs,
    double &render_time,
    std::filesystem::path result_img_dir,
    std::filesystem::path result_gt_dir,
    std::filesystem::path result_loss_dir,
    std::filesystem::path result_depth_dir,  // ← ADD
    std::string name_suffix = "");
```

## 📁 Output Structure

After changes, results will have:

```
results_pa6/
└── tum_rgbd_0/
    └── rgbd_dataset_freiburg1_desk/
        ├── image/                    # Rendered RGB (existing)
        ├── depth/                    # ← NEW: Rendered depth
        │   ├── 1305031453.359684_depth.png     # 16-bit PNG (for TSDF)
        │   ├── 1305031453.359684_depth_vis.jpg # Visualization
        │   └── ...
        ├── image_gt/
        └── CameraTrajectory_TUM.txt
```

## 🔧 Build & Run

```bash
cd /media/tam/DATA/3D/CG-photo

# Rebuild
cd build && make -j$(nproc) && cd ..

# Run PA6 to generate depth
./scripts/tum_rgbd_pa6.sh

# Check output
ls -lh results_pa6/tum_rgbd_0/rgbd_dataset_freiburg1_desk/depth/
```

## 🎯 Next: Generate Meshes from Rendered Depth

After implementing this, modify `generate_pa_meshes.py` to:

```python
# Read rendered depth instead of GT depth
depth_path = pa_result_path / dataset_name / "depth" / f"{timestamp}_depth.png"

# Read 16-bit PNG depth
depth_img = cv2.imread(str(depth_path), cv2.IMREAD_ANYDEPTH)
depth = depth_img.astype(np.float32) / 5000.0  # Convert back to meters

# Use with Open3D TSDF...
```

---

**Summary**: 
1. ✅ Depth rendering already exists (line 141-143 in gaussian_renderer.cpp)
2. ✅ Just need to save it to files
3. ✅ Use 16-bit PNG format (TUM standard)  
4. ✅ Add visualization with colormap

Bạn muốn tôi tạo file patch để apply changes tự động không? 😊
