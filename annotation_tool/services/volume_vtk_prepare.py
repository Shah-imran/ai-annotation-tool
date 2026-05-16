"""
Build PyVista datasets for 3D preview off the GUI thread (no QtInteractor / OpenGL).

Meshes and ImageData are created here; the widget attaches them on the main thread.
"""
import gc
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

import numpy as np

try:
    import pyvista as pv

    HAS_PYVISTA = True
except ImportError:
    HAS_PYVISTA = False

from .volume_preview_builder import VolumePreviewResult


class PreviewPrepareCancelled(Exception):
    """Worker should stop building."""


@dataclass
class PreviewVTKPayload:
    """Data to apply on the main-thread plotter."""

    result: VolumePreviewResult
    current_z: int
    generation: int
    primary: List[Tuple[str, Any, dict]]
    mask: List[Tuple[str, Any, dict]]
    volume_fallback: Optional[List[Tuple[str, Any, dict]]] = None


def _nonzero_sample(vol: np.ndarray) -> np.ndarray:
    flat = vol.ravel()
    if flat.size == 0:
        return flat
    nz = flat[flat > 0]
    return nz if nz.size > 500 else flat


def _intensity_range(vol: np.ndarray) -> Tuple[float, float]:
    sample = _nonzero_sample(vol)
    if sample.size == 0:
        return 0.0, 255.0
    lo = float(np.percentile(sample, 2))
    hi = float(np.percentile(sample, 98))
    if hi <= lo + 1:
        hi = lo + 1.0
    return lo, hi


def _opacity_transfer_solid(vol: np.ndarray) -> np.ndarray:
    sample = _nonzero_sample(vol)
    if sample.size == 0:
        return np.linspace(0.0, 0.8, 256, dtype=np.float32)

    noise = float(np.percentile(sample, 1))
    mid = float(np.percentile(sample, 45))
    bright = float(np.percentile(sample, 88))

    opacity = np.zeros(256, dtype=np.float32)
    for i in range(256):
        v = float(i)
        if v < noise:
            opacity[i] = 0.0
        elif v < mid:
            t = (v - noise) / max(1.0, mid - noise)
            opacity[i] = 0.06 + t * 0.42
        elif v < bright:
            t = (v - mid) / max(1.0, bright - mid)
            opacity[i] = 0.48 + t * 0.38
        else:
            t = min(1.0, (v - bright) / max(1.0, 255.0 - bright))
            opacity[i] = 0.86 + t * 0.12
    return opacity


def _opacity_transfer_soft(vol: np.ndarray) -> np.ndarray:
    lo, hi = _intensity_range(vol)
    opacity = np.zeros(256, dtype=np.float32)
    span = max(1.0, hi - lo)
    for i in range(256):
        if i < lo:
            continue
        t = min(1.0, (i - lo) / span)
        opacity[i] = t * 0.45
    return opacity


def _isosurface_levels(vol: np.ndarray, n_layers: int = 5) -> Tuple[float, ...]:
    sample = _nonzero_sample(vol)
    if sample.size == 0:
        return (80.0, 110.0, 140.0, 170.0)
    if n_layers <= 1:
        return (float(np.percentile(sample, 55)),)
    percents = np.linspace(32, 82, n_layers)
    return tuple(float(np.percentile(sample, p)) for p in percents)


def _adaptive_isosurface_layer_count(vol: np.ndarray) -> int:
    """Fewer mesh layers on large grids to cut peak RAM during contour + triangulate."""
    n = int(vol.size)
    if n > 64_000_000:
        return 2
    if n > 16_000_000:
        return 3
    if n > 4_000_000:
        return 4
    return 5


def make_image_grid(result: VolumePreviewResult) -> "pv.ImageData":
    vol = result.intensity_u8.astype(np.float32, copy=False)
    z_ds, h_ds, w_ds = vol.shape
    esz, esy, esx = result.spacing_effective_zyx
    grid = pv.ImageData()
    grid.dimensions = (w_ds, h_ds, z_ds)
    grid.spacing = (max(esx, 1e-6), max(esy, 1e-6), max(esz, 1e-6))
    grid.origin = (0.0, 0.0, 0.0)
    grid.point_data["values"] = vol.transpose(2, 1, 0).ravel(order="F")
    return grid


def _build_isosurface_commands(
    result: VolumePreviewResult,
    grid: "pv.ImageData",
    vol: np.ndarray,
    layered: bool,
    should_cancel: Callable[[], bool],
    title_hint: str = "",
    opaque_single: bool = False,
) -> List[Tuple[str, Any, dict]]:
    cmds: List[Tuple[str, Any, dict]] = []
    vmin, vmax = _intensity_range(vol)
    if opaque_single:
        levels = (result.isosurface_level,)
    elif layered:
        n_layers = _adaptive_isosurface_layer_count(vol)
        levels = _isosurface_levels(vol, n_layers=n_layers)
    else:
        levels = (result.isosurface_level,)

    n_levels = len(levels)
    for i, iso in enumerate(levels):
        if should_cancel():
            raise PreviewPrepareCancelled()
        surface = grid.contour([float(iso)], scalars="values")
        if surface.n_points == 0:
            continue
        surface = surface.clean().triangulate()
        surface = surface.compute_normals(
            auto_orient_normals=True, consistent_normals=True
        )
        opacity = 0.35 + 0.55 * (i + 1) / max(1, n_levels)
        if layered and n_levels > 1:
            opacity = 0.18 + 0.62 * (i + 1) / n_levels
        if opaque_single:
            mesh_kw = {
                "color": "#dcdcdc",
                "opacity": 1.0,
                "smooth_shading": True,
                "ambient": 0.18,
                "diffuse": 0.85,
                "specular": 0.35,
                "specular_power": 24,
                "show_scalar_bar": False,
                "edge_color": "#404040",
                "_detail_lit": True,
            }
        else:
            mesh_kw = {
                "scalars": "values",
                "cmap": "gray",
                "clim": [vmin, vmax],
                "opacity": min(1.0, opacity),
                "smooth_shading": True,
                "ambient": 0.45,
                "diffuse": 0.65,
                "specular": 0.3,
                "specular_power": 18,
                "show_scalar_bar": False,
            }
        cmds.append(("mesh", surface, mesh_kw))
        if i % 2 == 1:
            gc.collect()

    if not cmds:
        for fb in (40.0, 60.0, 90.0, 120.0):
            if should_cancel():
                raise PreviewPrepareCancelled()
            surface = grid.contour([fb], scalars="values")
            if surface.n_points > 0:
                surface = surface.clean().triangulate()
                cmds.append(
                    (
                        "mesh",
                        surface,
                        {
                            "scalars": "values",
                            "cmap": "gray",
                            "clim": [vmin, vmax],
                            "opacity": 0.85,
                            "smooth_shading": True,
                            "show_scalar_bar": False,
                        },
                    )
                )
                break
        if not cmds:
            cmds.append(
                (
                    "text",
                    "No surface at threshold — try Soft volume or Point cloud",
                    {"font_size": 10},
                )
            )
            return cmds

    if title_hint == "solid layers":
        cmds.append(
            (
                "text",
                "Solid volume — GPU raycast unavailable; showing layered surfaces.",
                {"font_size": 9, "color": "lightgray"},
            )
        )
    elif title_hint == "mip layers":
        cmds.append(
            (
                "text",
                "Soft volume / MIP — GPU raycast unavailable; showing layered surfaces.",
                {"font_size": 9, "color": "lightgray"},
            )
        )
    return cmds


def build_preview_payload(
    result: VolumePreviewResult,
    current_z: int,
    generation: int,
    should_cancel: Callable[[], bool],
) -> PreviewVTKPayload:
    """
    Construct VTK datasets (CPU-heavy) for later display on the GUI thread.

    Raises PreviewPrepareCancelled if should_cancel() is True during work.
    """
    if not HAS_PYVISTA:
        return PreviewVTKPayload(result, current_z, generation, [], [])

    primary: List[Tuple[str, Any, dict]] = []
    mask_cmds: List[Tuple[str, Any, dict]] = []
    volume_fallback: Optional[List[Tuple[str, Any, dict]]] = None

    if result.intensity_u8.size == 0:
        return PreviewVTKPayload(
            result,
            current_z,
            generation,
            [("text", "No volume data", {"font_size": 10})],
            [],
        )

    if should_cancel():
        raise PreviewPrepareCancelled()

    if result.mode == "point_cloud":
        if result.points_xyz is None or len(result.points_xyz) == 0:
            primary.append(("text", "No points above threshold", {"font_size": 10}))
        else:
            cloud = pv.PolyData(result.points_xyz)
            cloud["intensity"] = result.point_scalars
            primary.append(
                (
                    "mesh",
                    cloud,
                    {
                        "scalars": "intensity",
                        "cmap": "gray",
                        "point_size": 3.0,
                        "render_points_as_spheres": True,
                        "opacity": 0.9,
                        "show_scalar_bar": False,
                    },
                )
            )
    elif result.mode == "isosurface":
        grid = make_image_grid(result)
        primary.extend(
            _build_isosurface_commands(
                result, grid, result.intensity_u8, layered=True, should_cancel=should_cancel
            )
        )
    elif result.mode == "isosurface_lit":
        grid = make_image_grid(result)
        primary.extend(
            _build_isosurface_commands(
                result,
                grid,
                result.intensity_u8,
                layered=False,
                should_cancel=should_cancel,
                opaque_single=True,
            )
        )
    elif result.mode == "solid":
        vol = result.intensity_u8
        if vol.size == 0 or np.count_nonzero(vol) == 0:
            primary.append(("text", "No volume data", {"font_size": 10}))
        else:
            grid = make_image_grid(result)
            opacity_lut = _opacity_transfer_solid(vol)
            if float(opacity_lut.max()) < 0.05:
                opacity_lut = np.linspace(0.0, 0.75, 256, dtype=np.float32)
            esz, esy, esx = result.spacing_effective_zyx
            unit = max(min(esx, esy, esz) * 0.4, 1e-3)
            primary.append(
                (
                    "volume",
                    grid,
                    {
                        "scalars": "values",
                        "cmap": "gray",
                        "clim": [0.0, 255.0],
                        "opacity": opacity_lut.tolist(),
                        "blending": "composite",
                        "opacity_unit_distance": unit,
                        "shade": True,
                        "ambient": 0.35,
                        "diffuse": 0.7,
                        "specular": 0.2,
                        "specular_power": 12,
                        "show_scalar_bar": False,
                    },
                )
            )
            grid2 = make_image_grid(result)
            volume_fallback = _build_isosurface_commands(
                result,
                grid2,
                result.intensity_u8,
                layered=True,
                should_cancel=should_cancel,
                title_hint="solid layers",
            )
    else:
        vol = result.intensity_u8
        if vol.size == 0 or np.count_nonzero(vol) == 0:
            primary.append(("text", "No volume data", {"font_size": 10}))
        else:
            grid = make_image_grid(result)
            esz, esy, esx = result.spacing_effective_zyx
            unit = max(min(esx, esy, esz) * 0.4, 1e-3)
            mip_opacity = np.linspace(0.0, 1.0, 256, dtype=np.float32)
            primary.append(
                (
                    "volume",
                    grid,
                    {
                        "scalars": "values",
                        "cmap": "gray",
                        "clim": [0.0, 255.0],
                        "opacity": mip_opacity.tolist(),
                        "blending": "maximum",
                        "opacity_unit_distance": unit,
                        "shade": False,
                        "show_scalar_bar": False,
                    },
                )
            )
            grid2 = make_image_grid(result)
            volume_fallback = _build_isosurface_commands(
                result,
                grid2,
                result.intensity_u8,
                layered=True,
                should_cancel=should_cancel,
                title_hint="mip layers",
            )

    if should_cancel():
        raise PreviewPrepareCancelled()

    if result.mask_points_xyz is not None and len(result.mask_points_xyz) > 0:
        m = pv.PolyData(result.mask_points_xyz)
        m["class_id"] = result.mask_scalars
        mask_cmds.append(
            (
                "mesh",
                m,
                {
                    "scalars": "class_id",
                    "cmap": "Set1",
                    "point_size": 5.0,
                    "render_points_as_spheres": True,
                    "opacity": 0.95,
                    "show_scalar_bar": False,
                },
            )
        )

    return PreviewVTKPayload(
        result, current_z, generation, primary, mask_cmds, volume_fallback
    )
