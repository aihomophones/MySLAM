// Gradient Conflict Analysis - Add this code BEFORE loss.backward() in gaussian_mapper.cpp
// Location: Line ~722 (after computing all losses, before loss.backward())

// ============================================================================
// GRADIENT CONFLICT ANALYSIS LOGGING
// Uncomment this section to log gradient conflicts during training
// ============================================================================
#ifdef ENABLE_GRADIENT_CONFLICT_ANALYSIS
{
    // Log every N iterations
    const int log_interval = 100;
    
    if (getIteration() % log_interval == 0) {
        // Create tensor list of losses
        std::vector<std::pair<std::string, torch::Tensor>> individual_losses = {
            {"L1", (1.0 - lambda_dssim) * Ll1},
            {"DSSIM", lambda_dssim * (1.0 - loss_utils::ssim(masked_image, gt_image, device_type_))},
            {"L_align", lambda_align * L_align},
            {"L_var", lambda_var * L_var},
            {"L_iso", lambda_iso * L_iso}
        };
        
        // Store gradients for each loss
        std::vector<torch::Tensor> gradients;
        std::vector<std::string> loss_names;
        
        for (const auto& [name, l] : individual_losses) {
            // Zero gradients
            gaussians_->optimizer_->zero_grad(true);
            
            // Backward for this loss only
            l.backward(/*retain_graph=*/true);
            
            // Collect gradient (flatten xyz gradient)
            auto grad = gaussians_->xyz_.grad().flatten().clone();
            gradients.push_back(grad);
            loss_names.push_back(name);
        }
        
        // Compute pairwise cosine similarities
        std::cout << "[Gradient Analysis] Iter " << getIteration() << std::endl;
        
        for (size_t i = 0; i < gradients.size(); ++i) {
            for (size_t j = i + 1; j < gradients.size(); ++j) {
                auto g1 = gradients[i];
                auto g2 = gradients[j];
                
                float norm1 = g1.norm().item<float>();
                float norm2 = g2.norm().item<float>();
                
                float cos_sim = 0.0f;
                if (norm1 > 1e-8 && norm2 > 1e-8) {
                    cos_sim = (g1 * g2).sum().item<float>() / (norm1 * norm2);
                }
                
                const char* status = (cos_sim < -0.1) ? "CONFLICT" : 
                                     (cos_sim < 0.3) ? "WEAK" : "ALIGNED";
                
                std::cout << "  " << loss_names[i] << " vs " << loss_names[j] 
                          << ": cos=" << std::fixed << std::setprecision(3) << cos_sim
                          << " [" << status << "]" << std::endl;
            }
        }
        
        // Log gradient magnitudes
        std::cout << "  Gradient magnitudes:" << std::endl;
        for (size_t i = 0; i < gradients.size(); ++i) {
            float mag = gradients[i].norm().item<float>();
            std::cout << "    " << loss_names[i] << ": " << mag << std::endl;
        }
        
        // Zero gradients again for actual training
        gaussians_->optimizer_->zero_grad(true);
    }
}
#endif
// ============================================================================
// END GRADIENT CONFLICT ANALYSIS
// ============================================================================

// Original loss.backward() continues here:
// loss.backward();
