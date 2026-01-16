# 🔍 Root Cause Analysis: Why Depth Losses Don't Improve Results

## Discovered Issues

### Issue 1: L_iso Does NOT Use Depth Outputs
```cpp
// L_iso only uses scaling_ parameters
auto L_iso = loss_utils::isotropy_loss(gaussians_->scaling_, 1.5f, true);
```

- L_iso is a **regularizer on Gaussian shapes**, not a depth-related loss
- It penalizes needle-like Gaussians → encourages spherical shapes
- This doesn't actually improve depth estimation!

### Issue 2: L_align May Have Wrong Formulation
```cpp
L_align = |depth - median_depth|  // Self-supervised
```

- Compares **rendered depth** with **itself** (median of rendered depths)
- No ground truth supervision from Kinect
- If rendering is already wrong, this loss won't correct it

### Issue 3: Depth Backward Pass May Not Be Critical Path
The depth outputs (`depth`, `depth_sq`, `median_depth`) are used in losses, but:
- L_align gradients flow back through `depth` and `median_depth`
- But these affect `xyz_` positions, which are already optimized by L1/DSSIM
- Potential **conflicting optimization directions**

---

## Key Insight

The current "depth losses" don't actually provide new information:
1. **L_iso** = Shape regularizer (not depth-related)
2. **L_align** = Self-supervised (no GT depth)
3. **L_var** = Disabled due to conflicts

For meaningful improvement, need **direct sensor depth supervision**.

---

## Recommended Fix

Add **Sensor Depth Loss** using Kinect ground truth:

```cpp
// In training loop
auto kinect_depth = load_depth_image(depth_path);
auto L_sensor = loss_utils::l1_loss(rendered_depth, kinect_depth);
loss += lambda_sensor * L_sensor;
```

This provides:
- Direct supervision from real depth sensor
- Clear optimization target
- No ambiguity from self-supervised formulations
