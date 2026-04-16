"""
tensor_accel.py — VOS v0.5.0 hardware-accelerated tensor engine.

Provides a thin abstraction over NumPy (CPU) and PyTorch (GPU/DirectML)
so the rest of the VOS runtime can stay backend-agnostic.

GPU routing is enabled automatically when ``torch`` is importable **and** a
CUDA or DirectML device is available.  Pure-CPU installs (NumPy only) are
fully supported with zero code changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional PyTorch import — guarded so CPU-only environments work fine
# ---------------------------------------------------------------------------
try:
    import torch  # type: ignore[import]
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _TORCH_AVAILABLE = False


def _resolve_device(requested: Optional[str] = None) -> str:
    """Return the best available device string ('cuda', 'cpu', …)."""
    if not _TORCH_AVAILABLE:
        return "numpy"
    if requested:
        return requested
    if torch.cuda.is_available():
        return "cuda"
    # Windows DirectML via torch-directml
    try:
        import torch_directml  # type: ignore[import]
        return torch_directml.device()
    except ImportError:
        pass
    return "cpu"


class TensorEngine:
    """Hardware-accelerated tensor operations for the VOS pipeline.

    Parameters
    ----------
    device:
        Force a specific device string (``"cuda"``, ``"cpu"``, etc.).
        When *None* the best available device is selected automatically.
    dtype:
        NumPy / Torch dtype string used for all internal tensors.
        Defaults to ``"float32"``.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        dtype: str = "float32",
    ) -> None:
        self.device = _resolve_device(device)
        self.dtype = dtype
        self._backend: str = "torch" if _TORCH_AVAILABLE and self.device != "numpy" else "numpy"
        logger.info(
            "TensorEngine initialised — backend=%s device=%s dtype=%s",
            self._backend,
            self.device,
            self.dtype,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_tensor(self, data: Any) -> Any:
        """Convert *data* (list, ndarray, etc.) to a backend tensor."""
        arr = np.asarray(data, dtype=self.dtype)
        if self._backend == "torch":
            t = torch.from_numpy(arr)
            if isinstance(self.device, str) and self.device not in ("numpy", "cpu"):
                t = t.to(self.device)
            return t
        return arr

    def from_tensor(self, tensor: Any) -> np.ndarray:
        """Convert a backend tensor back to a NumPy array."""
        if self._backend == "torch" and _TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
            return tensor.detach().cpu().numpy()
        return np.asarray(tensor, dtype=self.dtype)

    def dot(self, a: Any, b: Any) -> Any:
        """Batched dot / matrix multiply."""
        if self._backend == "torch":
            ta, tb = self.to_tensor(a), self.to_tensor(b)
            return torch.matmul(ta, tb)
        return np.dot(np.asarray(a, dtype=self.dtype), np.asarray(b, dtype=self.dtype))

    def batch_compress(self, vectors: List[Any], ratio: float = 0.5) -> List[np.ndarray]:
        """Dimensionality-reduce a list of *vectors* by random projection.

        Parameters
        ----------
        vectors:
            Input vectors (each must have the same length).
        ratio:
            Fraction of dimensions to keep (0 < ratio ≤ 1).

        Returns
        -------
        list of np.ndarray
            Compressed vectors as NumPy arrays.
        """
        if not vectors:
            return []
        arr = np.asarray(vectors, dtype=self.dtype)          # (N, D)
        d_in = arr.shape[-1]
        d_out = max(1, int(d_in * ratio))

        rng = np.random.default_rng(seed=42)
        projection = rng.standard_normal((d_in, d_out)).astype(self.dtype) / np.sqrt(d_out)

        if self._backend == "torch" and _TORCH_AVAILABLE:
            t_arr = torch.from_numpy(arr)
            t_proj = torch.from_numpy(projection)
            if isinstance(self.device, str) and self.device not in ("numpy", "cpu"):
                t_arr = t_arr.to(self.device)
                t_proj = t_proj.to(self.device)
            compressed = torch.matmul(t_arr, t_proj).detach().cpu().numpy()
        else:
            compressed = arr @ projection

        return list(compressed)

    def stats(self, tensor: Any) -> Dict[str, float]:
        """Return basic descriptive statistics for *tensor*."""
        arr = self.from_tensor(tensor)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }
