"""
IO utilities for 3D volume slice stacks and NIfTI export.
"""
import json
import math
import os
import re
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

SLICE_PATTERN = re.compile(r"slice_(\d+)\.tif{1,2}$", re.IGNORECASE)


def discover_slice_files(scan_dir: str) -> List[str]:
    """Find and sort slice TIFF files in a scan directory."""
    if not os.path.isdir(scan_dir):
        return []

    files = []
    for name in os.listdir(scan_dir):
        if SLICE_PATTERN.match(name):
            files.append(os.path.join(scan_dir, name))

    def sort_key(path: str) -> int:
        m = SLICE_PATTERN.search(os.path.basename(path))
        return int(m.group(1)) if m else 0

    return sorted(files, key=sort_key)


def scan_id_from_path(scan_dir: str) -> str:
    """Derive scan id from folder name."""
    return os.path.basename(os.path.normpath(scan_dir))


def load_slice_tiff(path: str) -> np.ndarray:
    """Load one slice as uint16 grayscale array (H, W)."""
    with Image.open(path) as im:
        arr = np.array(im)
    if arr.ndim == 3:
        arr = arr[..., 0]
    return arr.astype(np.uint16, copy=False)


def validate_slice_stack(slice_paths: List[str]) -> Tuple[int, int]:
    """Return (height, width) if all slices match; raise ValueError otherwise."""
    if not slice_paths:
        raise ValueError("No slice files found")

    with Image.open(slice_paths[0]) as im:
        w, h = im.size

    for path in slice_paths[1:]:
        with Image.open(path) as im:
            if im.size != (w, h):
                raise ValueError(
                    f"Slice size mismatch: {os.path.basename(path)} "
                    f"expected ({w}, {h}), got {im.size}"
                )
    return h, w


def apply_window_level(
    slice_u16: np.ndarray,
    window_center: float,
    window_width: float,
) -> np.ndarray:
    """Map uint16 slice to uint8 using window/level (medical display)."""
    if window_width <= 0:
        window_width = 1.0
    low = window_center - window_width / 2.0
    high = window_center + window_width / 2.0
    scaled = (slice_u16.astype(np.float32) - low) / (high - low)
    scaled = np.clip(scaled, 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)


def interpolate_brush_line(
    y0: int, x0: int, y1: int, x1: int, radius: int
) -> List[Tuple[int, int]]:
    """Sample (y, x) points along a segment for a continuous brush stroke."""
    dist = math.hypot(y1 - y0, x1 - x0)
    if dist < 0.5:
        return [(y0, x0)]
    step = max(1.0, radius * 0.5)
    n = max(1, int(math.ceil(dist / step)))
    points: List[Tuple[int, int]] = []
    for i in range(n + 1):
        t = i / n
        y = int(round(y0 + t * (y1 - y0)))
        x = int(round(x0 + t * (x1 - x0)))
        if not points or points[-1] != (y, x):
            points.append((y, x))
    return points


def slice_to_preview_u8(
    slice_u16: np.ndarray,
    window_center: float,
    window_width: float,
    use_window_level: bool = False,
) -> np.ndarray:
    """
    Contrast for 3D preview: percentile stretch on 16-bit (recon-style detail).

    Unlike slice_to_display_u8 (high-byte / W-L for 2D viewing), this pulls
    mid-range structure into view so volume rendering looks more solid.
    """
    if use_window_level:
        return apply_window_level(slice_u16, window_center, window_width)

    flat = slice_u16.ravel()
    if flat.size == 0:
        return np.zeros_like(slice_u16, dtype=np.uint8)

    positive = flat[flat > 0]
    sample = positive if positive.size > 10000 else flat
    lo = float(np.percentile(sample, 1.0))
    hi = float(np.percentile(sample, 99.5))
    if hi <= lo:
        return (slice_u16 >> 8).astype(np.uint8)

    scaled = (slice_u16.astype(np.float32) - lo) / (hi - lo)
    return (np.clip(scaled, 0.0, 1.0) * 255.0).astype(np.uint8)


def slice_to_display_u8(
    slice_u16: np.ndarray,
    window_center: float,
    window_width: float,
    use_window_level: bool = False,
) -> np.ndarray:
    """
    Convert a uint16 slice for display.

    Default (use_window_level=False): map high 8 bits, matching typical TIFF
    viewers and avoiding a false circular mask from reconstruction fill values.

    use_window_level=True: apply window/level (contrast can emphasize the CT FOV edge).
    """
    if use_window_level:
        return apply_window_level(slice_u16, window_center, window_width)
    return (slice_u16 >> 8).astype(np.uint8)


def slice_window_defaults(slice_u16: np.ndarray) -> Tuple[float, float]:
    """Suggest window center/width using full slice range (faithful to raw TIFF)."""
    vmin = float(slice_u16.min())
    vmax = float(slice_u16.max())
    center = (vmin + vmax) / 2.0
    width = max(1.0, vmax - vmin)
    return center, width


def open_label_memmap(
    label_path: str,
    shape: Tuple[int, int, int],
    dtype: str = "uint8",
) -> np.memmap:
    """Open or create a memory-mapped label volume (Z, H, W)."""
    os.makedirs(os.path.dirname(label_path) or ".", exist_ok=True)
    mode = "r+" if os.path.exists(label_path) else "w+"
    mm = np.memmap(label_path, dtype=dtype, mode=mode, shape=shape)
    if mode == "w+":
        mm[:] = 0
        mm.flush()
    return mm


def save_segmentation_nifti(
    label_volume: np.ndarray,
    output_path: str,
    voxel_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> None:
    """Save label volume as NIfTI (.nii.gz)."""
    import nibabel as nib

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    affine = np.diag([voxel_spacing[0], voxel_spacing[1], voxel_spacing[2], 1.0])
    data = np.asarray(label_volume, dtype=np.uint8)
    img = nib.Nifti1Image(data, affine)
    nib.save(img, output_path)


def load_segmentation_nifti(path: str) -> np.ndarray:
    """Load label volume from NIfTI."""
    import nibabel as nib

    img = nib.load(path)
    return np.asarray(img.dataobj, dtype=np.uint8)


def save_intensity_nifti(
    slice_paths: List[str],
    output_path: str,
    voxel_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    progress_callback=None,
) -> None:
    """Stack TIFF slices and export as NIfTI intensity volume."""
    import nibabel as nib

    h, w = validate_slice_stack(slice_paths)
    z = len(slice_paths)
    volume = np.zeros((z, h, w), dtype=np.uint16)

    for i, path in enumerate(slice_paths):
        volume[i] = load_slice_tiff(path)
        if progress_callback:
            progress_callback(i + 1, z)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    affine = np.diag([voxel_spacing[0], voxel_spacing[1], voxel_spacing[2], 1.0])
    img = nib.Nifti1Image(volume, affine)
    nib.save(img, output_path)


def save_volume_meta(
    meta_path: str,
    scan_id: str,
    scan_dir: str,
    shape: Tuple[int, int, int],
    class_names: List[str],
    voxel_spacing: Tuple[float, float, float],
) -> None:
    """Write JSON metadata for a volume annotation session."""
    meta = {
        "scan_id": scan_id,
        "scan_dir": scan_dir,
        "shape_zyx": list(shape),
        "class_names": class_names,
        "voxel_spacing": list(voxel_spacing),
        "format_version": 1,
    }
    os.makedirs(os.path.dirname(meta_path) or ".", exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def load_volume_meta(meta_path: str) -> dict:
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)
