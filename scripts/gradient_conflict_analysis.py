#!/usr/bin/env python3
"""
Gradient Conflict Analysis Tool for Depth-Photo-SLAM

Phân tích hướng gradient của các hàm loss để phát hiện xung đột.
Dựa trên phương pháp cosine similarity giữa các gradient vectors.

Conflict xảy ra khi cos(θ) < 0, tức là gradients ngược hướng.

Loss functions trong Depth-Photo-SLAM:
1. L1 Loss (photometric)
2. DSSIM Loss (structural similarity)
3. L_align (depth alignment)
4. L_var (depth variance/uncertainty)
5. L_iso (isotropy regularization)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
import seaborn as sns
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class GradientStats:
    """Statistics for gradient conflict analysis."""
    cosine_similarity: float
    gradient_magnitude_ratio: float
    conflict_score: float  # 0 = aligned, 1 = orthogonal, 2 = opposing


class GradientConflictAnalyzer:
    """
    Analyzer for detecting gradient conflicts between multiple loss functions.
    
    Based on the paper: "Gradient Surgery for Multi-Task Learning"
    and "Conflict-Averse Gradient Descent for Multi-task Learning"
    """
    
    def __init__(self, param_names: List[str] = None):
        self.param_names = param_names or []
        self.history: Dict[str, List[float]] = defaultdict(list)
        self.gradient_cache: Dict[str, torch.Tensor] = {}
        
    def compute_individual_gradients(
        self,
        losses: Dict[str, torch.Tensor],
        params: List[torch.Tensor],
        retain_graph: bool = True
    ) -> Dict[str, torch.Tensor]:
        """
        Compute gradients for each loss separately.
        
        Args:
            losses: Dictionary of loss name -> loss tensor
            params: List of parameters to compute gradients for
            retain_graph: Whether to retain computational graph
            
        Returns:
            Dictionary of loss name -> flattened gradient vector
        """
        gradients = {}
        
        for loss_name, loss in losses.items():
            if loss is None or not loss.requires_grad:
                continue
                
            # Zero existing gradients
            for p in params:
                if p.grad is not None:
                    p.grad.zero_()
            
            # Compute gradient for this loss
            loss.backward(retain_graph=retain_graph)
            
            # Collect and flatten gradients
            grad_list = []
            for p in params:
                if p.grad is not None:
                    grad_list.append(p.grad.flatten().clone())
                else:
                    grad_list.append(torch.zeros(p.numel(), device=p.device))
            
            gradients[loss_name] = torch.cat(grad_list)
            
        return gradients
    
    def compute_cosine_similarity(
        self,
        grad1: torch.Tensor,
        grad2: torch.Tensor
    ) -> float:
        """Compute cosine similarity between two gradient vectors."""
        if grad1.norm() < 1e-8 or grad2.norm() < 1e-8:
            return 0.0
        return (grad1 @ grad2).item() / (grad1.norm().item() * grad2.norm().item())
    
    def compute_conflict_matrix(
        self,
        gradients: Dict[str, torch.Tensor]
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Compute pairwise cosine similarity matrix between gradients.
        
        Returns:
            conflict_matrix: NxN matrix of cosine similarities
            loss_names: List of loss names in order
        """
        loss_names = list(gradients.keys())
        n = len(loss_names)
        conflict_matrix = np.zeros((n, n))
        
        for i, name_i in enumerate(loss_names):
            for j, name_j in enumerate(loss_names):
                if i == j:
                    conflict_matrix[i, j] = 1.0
                else:
                    sim = self.compute_cosine_similarity(
                        gradients[name_i],
                        gradients[name_j]
                    )
                    conflict_matrix[i, j] = sim
                    
        return conflict_matrix, loss_names
    
    def analyze_conflicts(
        self,
        gradients: Dict[str, torch.Tensor]
    ) -> Dict[str, GradientStats]:
        """
        Analyze gradient conflicts between all pairs of losses.
        
        Returns:
            Dictionary of "loss1_vs_loss2" -> GradientStats
        """
        results = {}
        loss_names = list(gradients.keys())
        
        for i, name_i in enumerate(loss_names):
            for j, name_j in enumerate(loss_names):
                if i >= j:
                    continue
                    
                grad_i = gradients[name_i]
                grad_j = gradients[name_j]
                
                cos_sim = self.compute_cosine_similarity(grad_i, grad_j)
                
                # Magnitude ratio (smaller / larger)
                mag_i = grad_i.norm().item()
                mag_j = grad_j.norm().item()
                mag_ratio = min(mag_i, mag_j) / max(mag_i, mag_j) if max(mag_i, mag_j) > 1e-8 else 0
                
                # Conflict score: 0 = aligned (cos=1), 1 = orthogonal (cos=0), 2 = opposing (cos=-1)
                conflict_score = 1.0 - cos_sim
                
                key = f"{name_i}_vs_{name_j}"
                results[key] = GradientStats(
                    cosine_similarity=cos_sim,
                    gradient_magnitude_ratio=mag_ratio,
                    conflict_score=conflict_score
                )
                
                # Store history
                self.history[f"{key}_cos_sim"].append(cos_sim)
                self.history[f"{key}_conflict"].append(conflict_score)
                
        return results
    
    def detect_severe_conflicts(
        self,
        results: Dict[str, GradientStats],
        threshold: float = -0.1
    ) -> List[str]:
        """
        Detect loss pairs with severe gradient conflicts (cos_sim < threshold).
        
        Args:
            results: Analysis results from analyze_conflicts
            threshold: Cosine similarity threshold for conflict detection
            
        Returns:
            List of conflicting loss pair names
        """
        conflicts = []
        for pair_name, stats in results.items():
            if stats.cosine_similarity < threshold:
                conflicts.append(pair_name)
        return conflicts
    
    def get_gradient_magnitudes(
        self,
        gradients: Dict[str, torch.Tensor]
    ) -> Dict[str, float]:
        """Get the magnitude of each loss's gradient."""
        return {name: grad.norm().item() for name, grad in gradients.items()}
    
    def compute_gradient_dominance(
        self,
        gradients: Dict[str, torch.Tensor],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Compute how much each loss dominates the total gradient.
        
        Returns:
            Dictionary of loss name -> dominance percentage (0-100)
        """
        # Compute weighted gradients
        weighted_grads = {}
        for name, grad in gradients.items():
            w = weights.get(name, 1.0)
            weighted_grads[name] = grad * w
        
        # Compute total weighted gradient
        total_grad = sum(weighted_grads.values())
        total_norm = total_grad.norm().item()
        
        if total_norm < 1e-8:
            return {name: 0.0 for name in gradients}
        
        # Compute dominance as projection ratio
        dominance = {}
        for name, grad in weighted_grads.items():
            # Projection of individual gradient onto total
            proj = (grad @ total_grad).item() / (total_norm ** 2)
            dominance[name] = proj * 100  # As percentage
            
        return dominance


def plot_conflict_matrix(
    conflict_matrix: np.ndarray,
    loss_names: List[str],
    save_path: Optional[str] = None
):
    """Plot heatmap of gradient conflict matrix."""
    plt.figure(figsize=(10, 8))
    
    # Create heatmap
    sns.heatmap(
        conflict_matrix,
        xticklabels=loss_names,
        yticklabels=loss_names,
        annot=True,
        fmt='.2f',
        cmap='RdYlGn',  # Red = conflict, Green = aligned
        center=0,
        vmin=-1,
        vmax=1
    )
    
    plt.title('Gradient Conflict Matrix\n(Cosine Similarity: -1=Conflict, 0=Orthogonal, 1=Aligned)')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved conflict matrix to: {save_path}")
    else:
        plt.show()
    
    plt.close()


def plot_conflict_history(
    history: Dict[str, List[float]],
    save_path: Optional[str] = None
):
    """Plot conflict scores over training iterations."""
    plt.figure(figsize=(12, 6))
    
    for key, values in history.items():
        if '_cos_sim' in key:
            label = key.replace('_cos_sim', '').replace('_', ' ')
            plt.plot(values, label=label, alpha=0.7)
    
    plt.xlabel('Iteration')
    plt.ylabel('Cosine Similarity')
    plt.title('Gradient Alignment History\n(Below 0 = Conflict)')
    plt.axhline(y=0, color='r', linestyle='--', alpha=0.5, label='Conflict Threshold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved history plot to: {save_path}")
    else:
        plt.show()
    
    plt.close()


def analyze_depth_photo_slam_losses():
    """
    Demo analysis of Depth-Photo-SLAM loss configuration.
    
    Based on gaussian_mapper.cpp lines 698-722:
    - L1 loss: (1 - lambda_dssim) * Ll1
    - DSSIM loss: lambda_dssim * (1 - ssim)
    - L_align: lambda_align * depth_alignment_loss
    - L_var: lambda_var * uncertainty_variance_loss  
    - L_iso: lambda_iso * isotropy_loss
    """
    print("=" * 60)
    print("Depth-Photo-SLAM Gradient Conflict Analysis")
    print("=" * 60)
    
    # Current weights from code
    weights = {
        'L1': 0.8,           # (1 - 0.2) typical lambda_dssim
        'DSSIM': 0.2,        # typical lambda_dssim
        'L_align': 0.1,      # from code
        'L_var': 0.001,      # from code
        'L_iso': 0.01        # from code
    }
    
    print("\n📊 Current Loss Weights:")
    print("-" * 40)
    for name, weight in weights.items():
        print(f"  {name:12s}: {weight:.4f}")
    
    print("\n⚠️  Potential Conflicts Analysis:")
    print("-" * 40)
    
    conflicts = [
        ("L1 vs L_align", 
         "Photometric loss muốn match pixels, nhưng depth alignment có thể\n"
         "   đẩy Gaussians đến vị trí depth khác → gradient ngược hướng về position"),
        
        ("DSSIM vs L_var",
         "DSSIM ưu tiên structure, L_var muốn minimize variance.\n"
         "   Có thể conflict khi structure cần high-variance regions"),
        
        ("L_var vs L_iso",
         "L_var minimize depth variance, L_iso enforce round Gaussians.\n"
         "   Khi scale bị co về isotropic, depth variance có thể tăng"),
        
        ("L1 vs L_iso",
         "L1 cần Gaussians fit texture, L_iso force them to be round.\n"
         "   Needle-like Gaussians tốt cho edges nhưng bị L_iso penalize"),
    ]
    
    for pair, explanation in conflicts:
        print(f"\n  🔴 {pair}:")
        print(f"     {explanation}")
    
    print("\n💡 Recommendations:")
    print("-" * 40)
    print("""
  1. REDUCE lambda_align (0.1 → 0.01-0.05):
     Depth loss đang quá mạnh so với photometric loss
     
  2. REMOVE or REDUCE L_iso:
     Isotropy loss có thể harmful cho scene với edges/texture
     
  3. SCHEDULE weights:
     - Early training: Higher photometric (L1, DSSIM)
     - Later training: Add depth losses gradually
     
  4. USE Gradient Surgery:
     Project conflicting gradients để loại bỏ thành phần xung đột
""")
    
    return weights


def simulate_gradient_conflict():
    """
    Simulate gradient conflict với synthetic data để demo.
    """
    print("\n" + "=" * 60)
    print("Simulated Gradient Conflict Demo")
    print("=" * 60)
    
    # Create synthetic parameters
    torch.manual_seed(42)
    params = [torch.randn(100, requires_grad=True)]
    
    # Create synthetic losses with known gradient relationships
    x = params[0]
    
    # Losses that should align (both minimize similar objectives)
    loss_l1 = x.abs().mean()
    loss_dssim = (x ** 2).mean()  # Aligned with L1
    
    # Loss that conflicts (wants to increase what others decrease)
    loss_conflict = -x.mean()  # Wants to maximize, others minimize
    
    # Orthogonal loss
    loss_ortho = (x[::2] - x[1::2]).abs().mean()
    
    losses = {
        'L1': loss_l1,
        'DSSIM': loss_dssim,
        'L_conflict': loss_conflict,
        'L_ortho': loss_ortho
    }
    
    # Analyze
    analyzer = GradientConflictAnalyzer()
    gradients = analyzer.compute_individual_gradients(losses, params)
    results = analyzer.analyze_conflicts(gradients)
    matrix, names = analyzer.compute_conflict_matrix(gradients)
    
    print("\n📊 Gradient Conflict Matrix:")
    print("-" * 50)
    print(f"{'':15s}", end='')
    for name in names:
        print(f"{name:12s}", end='')
    print()
    
    for i, name_i in enumerate(names):
        print(f"{name_i:15s}", end='')
        for j in range(len(names)):
            val = matrix[i, j]
            color = "🟢" if val > 0.7 else ("🟡" if val > 0 else "🔴")
            print(f"{color} {val:+.2f}    ", end='')
        print()
    
    print("\n📈 Detailed Analysis:")
    print("-" * 50)
    for pair_name, stats in results.items():
        status = "✅ Aligned" if stats.cosine_similarity > 0.5 else \
                 ("⚠️ Weak" if stats.cosine_similarity > 0 else "❌ CONFLICT")
        print(f"  {pair_name:25s}: cos={stats.cosine_similarity:+.3f}  {status}")
    
    # Gradient magnitudes
    mags = analyzer.get_gradient_magnitudes(gradients)
    print("\n📊 Gradient Magnitudes:")
    print("-" * 50)
    for name, mag in sorted(mags.items(), key=lambda x: -x[1]):
        bar = "█" * int(mag / max(mags.values()) * 30)
        print(f"  {name:15s}: {mag:.4f} {bar}")


if __name__ == "__main__":
    # Run analysis
    weights = analyze_depth_photo_slam_losses()
    
    # Run simulation demo
    simulate_gradient_conflict()
    
    print("\n" + "=" * 60)
    print("To integrate into training, add gradient analysis hook")
    print("before loss.backward() in gaussian_mapper.cpp")
    print("=" * 60)
