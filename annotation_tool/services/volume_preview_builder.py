"""
Build downsampled 3D previews (MIP volume / point cloud) from lazy slice stacks.
"""
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

from .preview_quality import clamp_level, params_for_level
from .volume_io import load_slice_tiff, slice_to_preview_u8


class PreviewBuildCancelled(Exception):
    """Raised when a background preview build is cancelled."""


@dataclass
class VolumePreviewResult:
    """Data for the 3D preview widget."""

    mode: str  # "isosurface_lit" | "point_cloud" (legacy modes still accepted)
    intensity_u8: np.ndarray  # (Z', H', W') downsampled
    spacing_zyx: Tuple[float, float, float]  # (sz, sy, sx) per full-resolution voxel
    shape_zyx: Tuple[int, int, int]  # full volume shape (Z, H, W)
    stride_zyx: Tuple[int, int, int]
    z_indices: Tuple[int, ...]  # full Z index for each downsampled Z slab
    isosurface_level: float = 128.0
    points_xyz: Optional[np.ndarray] = None  # (N, 3) physical coords (x, y, z)
    point_scalars: Optional[np.ndarray] = None  # (N,) intensity 0-255
    mask_points_xyz: Optional[np.ndarray] = None
    mask_scalars: Optional[np.ndarray] = None  # class ids
    preview_level: int = 5
    preview_z_range: Tuple[int, int] = (0, 0)  # inclusive full-volume Z indices used
    native_resolution: bool = False  # stride 1×1×1 (no XY/Z downsampling for loaded slabs)
    # Point-cloud rendering hint (size only — the rest stays hard-coded so the
    # point-cloud look is consistent across builds).
    point_size: float = 3.0
    # Isosurface ("isosurface_lit") mesh color as a `#RRGGBB` string.
    iso_color: str = "#dcdcdc"

    @property
    def spacing_effective_zyx(self) -> Tuple[float, float, float]:
        """Voxel spacing between downsampled grid points in physical units."""
        sz, sy, sx = self.spacing_zyx
        stz, sty, stx = self.stride_zyx
        return (sz * stz, sy * sty, sx * stx)

    @property
    def physical_extent_xyz(self) -> Tuple[float, float, float]:
        """Physical size (x, y, z) of the full volume."""
        z, h, w = self.shape_zyx
        sz, sy, sx = self.spacing_zyx
        return ((w - 1) * sx, (h - 1) * sy, (z - 1) * sz)


def _max_pool_2d(block: np.ndarray, sy: int, sx: int) -> np.ndarray:
    """Max-pool including edge pixels (shape matches ceil(h/sy) × ceil(w/sx))."""
    if sy <= 1 and sx <= 1:
        return block.astype(np.uint8, copy=True)

    h, w = block.shape
    h_ds = (h + sy - 1) // sy
    w_ds = (w + sx - 1) // sx
    pad_h = h_ds * sy - h
    pad_w = w_ds * sx - w
    if pad_h or pad_w:
        block = np.pad(
            block,
            ((0, max(0, pad_h)), (0, max(0, pad_w))),
            mode="edge",
        )
    reshaped = block.reshape(h_ds, sy, w_ds, sx)
    return reshaped.max(axis=(1, 3)).astype(np.uint8)


def _auto_stride(
    shape_zyx: Tuple[int, int, int],
    target_max_voxels: int = 12_000_000,
    use_all_z_slices: bool = True,
) -> Tuple[int, int, int]:
    """
    Pick stride for 3D preview downsampling.

    By default uses **every Z slice** (full stack) and only reduces XY so the
    preview volume fits in RAM (~tens of MB for 612×268×268, not ~10 GB full res).
    """
    z, h, w = shape_zyx
    if use_all_z_slices:
        z_slabs = max(1, z)
        pixels_per_slice = max(1, target_max_voxels // z_slabs)
        factor = max(1.0, ((h * w) / pixels_per_slice) ** 0.5)
        sy = max(1, int(round(factor)))
        sx = max(1, int(round(factor)))
        return (1, sy, sx)

    total = max(1, z * h * w)
    factor = max(1.0, (total / target_max_voxels) ** (1.0 / 3.0))
    sz = max(1, int(round(factor)))
    sy = max(1, int(round(factor)))
    sx = max(1, int(round(factor)))
    return sz, sy, sx


def build_downsampled_intensity(
    slice_paths: List[str],
    stride_zyx: Optional[Tuple[int, int, int]] = None,
    source_z_indices: Optional[List[int]] = None,
    window_center: float = 0.0,
    window_width: float = 1.0,
    use_window_level: bool = False,
    use_max_pool: bool = True,
    target_max_voxels: int = 12_000_000,
    use_all_z_slices: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, Tuple[int, int, int], Tuple[int, ...]]:
    """
    Load and downsample the intensity stack to uint8 (Z', H', W').

    Returns:
        volume_u8, stride_zyx used, z_indices (full-volume Z for each downsampled slab)
    """
    if not slice_paths:
        return np.zeros((0, 0, 0), dtype=np.uint8), (1, 1, 1), ()

    from PIL import Image

    with Image.open(slice_paths[0]) as im:
        h, w = im.size[1], im.size[0]
    z_count = len(slice_paths)
    shape = (z_count, h, w)

    if stride_zyx is None:
        stride_zyx = _auto_stride(
            shape,
            target_max_voxels=target_max_voxels,
            use_all_z_slices=use_all_z_slices,
        )
    sz, sy, sx = stride_zyx

    if source_z_indices is None:
        source_z_indices = list(range(z_count))
    if len(source_z_indices) != z_count:
        source_z_indices = list(range(z_count))

    local_z = list(range(0, z_count, sz))
    if not local_z:
        local_z = [0]
    z_indices = tuple(source_z_indices[i] for i in local_z)

    h_ds = max(1, (h + sy - 1) // sy)
    w_ds = max(1, (w + sx - 1) // sx)
    out = np.zeros((len(local_z), h_ds, w_ds), dtype=np.uint8)

    for out_z, z_local in enumerate(local_z):
        if should_cancel and should_cancel():
            raise PreviewBuildCancelled()
        sl = load_slice_tiff(slice_paths[z_local])
        u8 = slice_to_preview_u8(sl, window_center, window_width, use_window_level)
        if use_max_pool and (sy > 1 or sx > 1):
            pooled = _max_pool_2d(u8, sy, sx)
            out[out_z, : pooled.shape[0], : pooled.shape[1]] = pooled
        else:
            out[out_z] = u8[::sy, ::sx][:h_ds, :w_ds]
        if progress_callback:
            progress_callback(out_z + 1, len(local_z))

    return out, stride_zyx, z_indices


def build_mask_from_memmap(
    label_path: str,
    shape_zyx: Tuple[int, int, int],
    stride_zyx: Tuple[int, int, int],
    spacing_zyx: Tuple[float, float, float],
    z_full_indices: Optional[List[int]] = None,
    max_points: int = 120_000,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Read label memmap on the worker thread (thread-safe, no Qt)."""
    if not label_path or not os.path.isfile(label_path):
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.float32)

    z, h, w = shape_zyx
    if z <= 0 or h <= 0 or w <= 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.float32)

    labels = np.memmap(label_path, dtype=np.uint8, mode="r", shape=(z, h, w))

    def accessor(z_index: int) -> np.ndarray:
        if should_cancel and should_cancel():
            raise PreviewBuildCancelled()
        return np.asarray(labels[z_index])

    return build_mask_point_cloud(
        accessor,
        stride_zyx,
        spacing_zyx,
        z_full_indices=z_full_indices,
        num_slices=z,
        max_points=max_points,
    )


def build_axial_mip(intensity_u8: np.ndarray) -> np.ndarray:
    """Max intensity projection along Z (returns H', W')."""
    if intensity_u8.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    return np.max(intensity_u8, axis=0).astype(np.uint8)


def build_point_cloud(
    intensity_u8: np.ndarray,
    spacing_zyx: Tuple[float, float, float],
    stride_zyx: Tuple[int, int, int],
    z_indices: Tuple[int, ...],
    threshold: int = 25,
    max_points: int = 250_000,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract subsampled surface points in full-volume physical coordinates."""
    if intensity_u8.size == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.uint8)

    sz, sy, sx = spacing_zyx
    stz, sty, stx = stride_zyx
    z_map = np.asarray(z_indices, dtype=np.float32)

    mask = intensity_u8 >= threshold
    if not mask.any():
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.uint8)

    zz, yy, xx = np.nonzero(mask)
    scalars = intensity_u8[zz, yy, xx]
    points = np.column_stack(
        (
            xx.astype(np.float32) * stx * sx,
            yy.astype(np.float32) * sty * sy,
            z_map[zz] * sz,
        )
    )

    if len(points) > max_points:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(points), size=max_points, replace=False)
        points = points[idx]
        scalars = scalars[idx]

    return points, scalars


def build_mask_point_cloud(
    label_volume_accessor: Callable[[int], np.ndarray],
    stride_zyx: Tuple[int, int, int],
    spacing_zyx: Tuple[float, float, float],
    z_full_indices: Optional[List[int]] = None,
    num_slices: int = 0,
    max_points: int = 120_000,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sparse labeled voxels for overlay (subsampled per slice).

    label_volume_accessor(z) -> 2D uint8 label slice at full resolution.
    """
    stz, sty, stx = stride_zyx
    spz, spy, spx = spacing_zyx
    points_list = []
    scalars_list = []

    if z_full_indices is None:
        z_iter = list(range(0, max(0, num_slices), stz))
    else:
        z_iter = list(z_full_indices[::stz])

    for z in z_iter:
        if z < 0 or (num_slices > 0 and z >= num_slices):
            continue
        labels = label_volume_accessor(z)
        if labels is None or labels.max() == 0:
            continue
        sub = labels[::sty, ::stx]
        yy, xx = np.nonzero(sub)
        if len(yy) == 0:
            continue
        pts = np.column_stack(
            (
                xx.astype(np.float32) * stx * spx,
                yy.astype(np.float32) * sty * spy,
                np.full(len(yy), z, dtype=np.float32) * spz,
            )
        )
        points_list.append(pts)
        scalars_list.append(sub[yy, xx].astype(np.float32))

    if not points_list:
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.float32)

    points = np.vstack(points_list)
    scalars = np.concatenate(scalars_list)

    if len(points) > max_points:
        rng = np.random.default_rng(1)
        idx = rng.choice(len(points), size=max_points, replace=False)
        points = points[idx]
        scalars = scalars[idx]

    return points, scalars


def build_preview(
    slice_paths: List[str],
    spacing_xyz: Tuple[float, float, float],
    mode: str = "point_cloud",
    stride_zyx: Optional[Tuple[int, int, int]] = None,
    source_z_indices: Optional[List[int]] = None,
    full_shape_zyx: Optional[Tuple[int, int, int]] = None,
    window_center: float = 0.0,
    window_width: float = 1.0,
    use_window_level: bool = False,
    label_path: str = "",
    label_shape: Tuple[int, int, int] = (0, 0, 0),
    include_mask: bool = True,
    preview_level: int = 5,
    native_full_volume: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    # Point-cloud-only overrides:
    point_size: float = 3.0,
    point_threshold_override: Optional[int] = None,
    # Isosurface-only overrides:
    iso_color: str = "#dcdcdc",
) -> VolumePreviewResult:
    """
    Build preview payload for the 3D widget.

    spacing_xyz: (sx, sy, sz) physical spacing per image x, y, z.
    source_z_indices: full-volume Z index for each entry in slice_paths.
    full_shape_zyx: complete scan shape (for slice plane); defaults from slice_paths.
    """
    sx, sy, sz = spacing_xyz
    spacing_zyx = (sz, sy, sx)

    level = clamp_level(preview_level)
    level_params = params_for_level(mode, level)

    # Anything that builds a 3D grid (anything other than point_cloud) benefits
    # from max-pool downsampling to preserve features.
    use_max_pool = mode != "point_cloud"

    z_count = len(slice_paths)
    if source_z_indices is None:
        source_z_indices = list(range(z_count))

    # Full grid: budget at least Z×H×W so _auto_stride yields (1,1,1). RAM-heavy.
    native_effective = bool(native_full_volume) and z_count > 0
    h_full_dim, w_full_dim = 0, 0
    if slice_paths:
        from PIL import Image

        with Image.open(slice_paths[0]) as im:
            w_full_dim, h_full_dim = im.size

    if native_effective and h_full_dim > 0 and w_full_dim > 0:
        full_voxels = z_count * h_full_dim * w_full_dim
        target_voxels = max(level_params.target_max_voxels, full_voxels)
        use_all_z_for_stride = True
    else:
        native_effective = False
        target_voxels = level_params.target_max_voxels
        use_all_z_for_stride = level_params.use_all_z_slices

    intensity, stride, z_indices = build_downsampled_intensity(
        slice_paths,
        stride_zyx=stride_zyx,
        source_z_indices=source_z_indices,
        window_center=window_center,
        window_width=window_width,
        use_window_level=use_window_level,
        use_max_pool=use_max_pool,
        target_max_voxels=target_voxels,
        use_all_z_slices=use_all_z_for_stride,
        progress_callback=progress_callback,
        should_cancel=should_cancel,
    )

    h_full, w_full = h_full_dim, w_full_dim
    if full_shape_zyx and len(full_shape_zyx) == 3:
        shape_zyx = full_shape_zyx
    else:
        shape_zyx = (z_count, h_full, w_full)

    z_lo = min(source_z_indices) if source_z_indices else 0
    z_hi = max(source_z_indices) if source_z_indices else 0

    points, scalars = None, None
    if mode == "point_cloud" and intensity.size > 0:
        threshold_value = (
            int(point_threshold_override)
            if point_threshold_override is not None
            else level_params.point_threshold
        )
        threshold_value = max(0, min(255, threshold_value))
        points, scalars = build_point_cloud(
            intensity,
            spacing_zyx,
            stride,
            z_indices,
            threshold=threshold_value,
            max_points=level_params.point_max_points,
        )

    mask_pts, mask_sc = None, None
    if include_mask and label_path and label_shape[0] > 0:
        mask_pts, mask_sc = build_mask_from_memmap(
            label_path,
            label_shape,
            stride,
            spacing_zyx,
            z_full_indices=source_z_indices,
            should_cancel=should_cancel,
        )

    # Restore the original isosurface threshold logic: only the layered
    # "isosurface" mode gets the 55th-percentile auto-pick; the opaque
    # "isosurface_lit" mode keeps the fixed 128.0 default that produced
    # the look we had before the per-mode panel knobs were added.
    iso_level = 128.0
    if mode == "isosurface" and intensity.size > 0:
        nonzero = intensity[intensity > 0]
        if nonzero.size > 0:
            iso_level = float(np.percentile(nonzero, 55))

    # Normalise iso color: must look like `#rrggbb`. Fall back to the default
    # neutral gray on anything weird so downstream VTK code never blows up.
    iso_hex = (iso_color or "#dcdcdc").strip()
    if not (iso_hex.startswith("#") and len(iso_hex) == 7):
        iso_hex = "#dcdcdc"

    return VolumePreviewResult(
        mode=mode,
        intensity_u8=intensity,
        isosurface_level=iso_level,
        spacing_zyx=spacing_zyx,
        shape_zyx=shape_zyx,
        stride_zyx=stride,
        z_indices=z_indices,
        preview_level=level,
        preview_z_range=(z_lo, z_hi),
        native_resolution=native_effective,
        points_xyz=points,
        point_scalars=scalars,
        mask_points_xyz=mask_pts if mask_pts is not None and len(mask_pts) else None,
        mask_scalars=mask_sc if mask_sc is not None and len(mask_sc) else None,
        point_size=float(max(0.5, point_size)),
        iso_color=iso_hex,
    )
