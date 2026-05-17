# 3D Volume Annotation — User Guide

This guide covers the **full 3D volume annotation workflow**: loading scans, painting labels in 2D, using the 3D preview to navigate, saving work, and exporting results.

For implementation details, see [`3d_preview_technical.md`](./3d_preview_technical.md).

---

## 1. Overview

| Area | What you use it for |
|------|---------------------|
| **2D slice viewer (left)** | Paint and erase voxel labels with the brush |
| **Right control panel** | Scan I/O, slice navigation, classes, brush, display, 3D preview settings |
| **3D preview window (separate)** | Orbit the volume, see slice position, adjust lighting, export snapshot/mesh |

The 2D viewer is where annotation happens. The 3D preview helps you **find** structures and **check** labels — it does not replace the slice canvas.

---

## 2. Getting started

### Switch to 3D Volume mode

Under the menubar, click **3D Volume** (next to **2D Bounding Boxes**).

The app pre-starts the 3D helper process in the background so the first preview builds faster.

### Load a scan

1. **Load Scan Folder…** — choose a folder of `slice_*.tif` files.
2. The 2D viewer shows the first slice; the panel shows slice count and scan id.

Labels are stored automatically in a memmap file next to your annotations folder (`*_labels.dat`). You do not need to save before painting.

---

## 3. Annotating in 2D (main workflow)

### Navigate slices

- **Slice slider** or **Prev / Next** on the panel  
- **A** / **D** keyboard shortcuts (prev / next)  
- The **3D preview** shows a cyan plane at the current Z (after you build a preview)

### Brush

| Control | Action |
|---------|--------|
| **Radius** spin box | Brush size in pixels |
| **Eraser** toggle (switch) | ON = erase to background (class 0); OFF = paint with selected class |
| Mouse wheel (no Ctrl) | Change brush radius |
| Left-drag | Paint or erase stroke |

### Classes

The **Class** dropdown lists every class from your classes file (except “background”, which is id 0).

- Select a class **before** painting.
- Each class has a **distinct overlay color** in the 2D viewer (classes 5, 6, 7… are supported — not limited to the first four).
- Painted voxels use the **numeric class id** shown in the combo (e.g. `5: crack`).

### Display (2D brightness & contrast)

**Display Brightness & Contrast** affects how the **scan** looks in 2D (and what intensities feed the next 3D rebuild):

- **Brightness** — midpoint of the gray ramp  
- **Contrast** — width of the intensity range mapped to gray  
- **Reset Display** — auto contrast like a TIFF viewer  

Adjust these until features are visible, then rebuild 3D if needed.

### Undo

Brush strokes support undo/redo via the main menu (when wired) or your usual shortcuts if enabled in your build.

---

## 4. Using the 3D preview

### Build a preview

1. In **3D Preview** on the right panel, choose **Mode**:
   - **Isosurface (opaque, lit)** — solid surface, best for shape and voids  
   - **Point cloud** — fast, see-through dots  
2. Set **Z stride** / **XY stride** (higher = faster, lower resolution).  
3. Click **Start preview**.  
4. Click **Show 3D window** if the window is hidden.

Status text on the panel shows progress; the main window stays responsive (work runs in a separate process).

### Mode-specific options

**Isosurface**

- **Surface color** — click the color swatch to pick mesh color (default light gray).  
- Rebuild after changing color.

**Point cloud**

- **Density** (1–5), **Point size**, **Threshold** (or auto from density).

### 3D window controls

| Control | Effect |
|---------|--------|
| Left-drag | Orbit |
| Wheel | Zoom |
| Middle-drag / Shift+drag | Pan |
| **Home** | Reset camera |
| **Brightness** slider (bottom) | Scene lighting (instant, no rebuild) |
| **Save snapshot…** | High-res PNG (3× resolution) |
| **Export 3D model…** | STL / OBJ / VTP / PLY / VTK of the isosurface mesh |

**Export notes**

- **Snapshot** — works whenever the 3D view is visible.  
- **3D model** — only after an **isosurface** build (not point cloud).  
- Files are written where you choose in the save dialog (defaults to your home folder).

### Slice plane in 3D

When you change the 2D slice, the cyan plane in 3D moves to match — use this to relate 2D edits to 3D structure.

### Label overlay in 3D

Enable **Show label overlay** before starting a preview to see annotated voxels as colored points in the 3D scene.

---

## 5. Recommended annotation flow

```text
Load scan
    → Tune 2D brightness/contrast
    → Point cloud preview (stride 2) for quick overview
    → Find region of interest in 3D; note Z range
    → (Optional) Limit preview to slice range
    → Isosurface preview for detail
    → Paint class-by-class in 2D (toggle Eraser off/on)
    → Toggle label overlay in 3D to QC
    → Save labels + Export NIfTI when done
```

1. **Explore** with point cloud + strides.  
2. **Refine** with isosurface on the Z range you care about.  
3. **Annotate** in 2D, switching classes from the dropdown.  
4. **QC** with 3D overlay and slice plane.  
5. **Save** and **export**.

---

## 6. Saving and loading

### Save labels (session)

**Save Labels** writes:

- The memmap label volume (already on disk; this flushes it)  
- `*_meta.json` with scan id, shape, class names, voxel spacing  

Use this often during long sessions.

### Export NIfTI segmentation

**Export NIfTI Segmentation…** saves `uint8` labels as `.nii.gz` with voxel spacing from preferences.

- Default path: annotations folder, `{scan_id}_seg.nii.gz`  
- Shape must match the loaded scan  

### Load NIfTI segmentation

**Load NIfTI Segmentation…** replaces the current label volume from a `.nii.gz` or `.nii` file.

- Scan must already be loaded  
- File shape must match `(Z, H, W)` of the scan  
- On success, the 2D overlay updates immediately  

### Auto-load on scan open

If `{scan_id}_seg.nii.gz` exists in the annotations folder when you load that scan, it is imported automatically.

---

## 7. File layout (typical)

```text
annotations/
  myscan_labels.dat      # memmap labels (binary)
  myscan_meta.json       # metadata
  myscan_seg.nii.gz      # exported segmentation (optional)
```

Logs (if enabled): `logs/annotation_tool.log` in the working directory.

---

## 8. Keyboard shortcuts (3D volume mode)

| Key | Action |
|-----|--------|
| A / D | Previous / next slice |
| Ctrl+S | Save labels (if bound in your build) |
| Wheel | Brush size |
| Ctrl+wheel | Zoom 2D slice |
| Middle-drag | Pan 2D |
| Home (2D focused) | Reset 2D zoom |
| Home (3D window focused) | Reset 3D camera |

---

## 9. Troubleshooting

### Class 5+ paints but I don’t see color

Fixed in current builds: overlay colors are generated for all class ids up to 255. Rebuild the app if you still only see four colors.

### Eraser still paints a color

Turn **Eraser** ON (green switch). When ON, strokes set voxels to background (0).

### Start Preview grayed out

A build is running, or the child process failed. Click **Stop**, or switch to 2D and back to 3D to reset. Check `logs/annotation_tool.log`.

### NIfTI export/load fails

- Install: `pip install nibabel`  
- Shape must match the scan exactly  
- See status message on the main window for the exact error  

### Export 3D model disabled / fails

Build an **Isosurface** preview first. Point clouds are not exported as a single surface mesh.

### 3D snapshot is black

Rotate the model into view, increase **Brightness** in the 3D window, then save again.

---

## 10. Performance tips

- Use **Z stride 2**, **XY stride 2** for first-pass 3D.  
- Use **point cloud** to scout; switch to **isosurface** for detail.  
- **Native resolution** only when you need full grid quality (high RAM).  
- Hide the 3D window when not needed to save GPU time.
