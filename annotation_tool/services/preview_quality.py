"""
Preview quality levels (1–5) and per-mode build parameters.
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PreviewLevelParams:
    """Resolved downsampling / budget for one build."""

    level: int
    target_max_voxels: int
    use_all_z_slices: bool
    point_max_points: int
    point_threshold: int


# Level 5 = largest budget in this table (still subsamples huge stacks to fit ~28M voxels).
# For true full-grid loading, use UI "Native resolution" (build_preview native_full_volume).
# Level 1 = fastest (mode-specific budgets).
_MODE_BASE_VOXELS = {
    "isosurface": 28_000_000,
    "solid": 28_000_000,
    "mip": 18_000_000,
    "point_cloud": 10_000_000,
}

_MODE_BASE_POINTS = {
    "isosurface": 0,
    "solid": 0,
    "mip": 0,
    "point_cloud": 280_000,
}

_LEVEL_VOXEL_SCALE = {
    1: 0.06,
    2: 0.15,
    3: 0.35,
    4: 0.65,
    5: 1.0,
}

_LEVEL_POINT_SCALE = {
    1: 0.08,
    2: 0.2,
    3: 0.45,
    4: 0.75,
    5: 1.0,
}

# Below this level, skip slices in Z (3D stride) as well as XY.
_USE_ALL_Z_MIN_LEVEL = 3


def clamp_level(level: int) -> int:
    return max(1, min(5, int(level)))


def params_for_level(mode: str, level: int) -> PreviewLevelParams:
    """
    Map quality level 1–5 to voxel budget and Z sampling.

    Levels 4–5: every slice in range, increasing XY detail.
    Levels 1–2: skip slices in Z and downsample XY more (faster).
    """
    level = clamp_level(level)
    mode_key = mode if mode in _MODE_BASE_VOXELS else "mip"
    base_voxels = _MODE_BASE_VOXELS[mode_key]
    voxel_scale = _LEVEL_VOXEL_SCALE[level]
    target = max(500_000, int(base_voxels * voxel_scale))

    base_pts = _MODE_BASE_POINTS.get(mode_key, 200_000)
    max_pts = max(10_000, int(base_pts * _LEVEL_POINT_SCALE[level])) if base_pts else 0

    thresholds = {1: 35, 2: 30, 3: 25, 4: 22, 5: 18}
    if mode_key == "point_cloud":
        thresholds = {1: 40, 2: 35, 3: 28, 4: 24, 5: 20}

    return PreviewLevelParams(
        level=level,
        target_max_voxels=target,
        use_all_z_slices=level >= _USE_ALL_Z_MIN_LEVEL,
        point_max_points=max_pts if mode_key == "point_cloud" else 250_000,
        point_threshold=thresholds[level],
    )


def level_description(mode: str, level: int) -> str:
    level = clamp_level(level)
    p = params_for_level(mode, level)
    z_part = "all slices" if p.use_all_z_slices else "skipped Z"
    return f"Level {level}/5 · {z_part} · ~{p.target_max_voxels // 1_000_000}M voxels"
