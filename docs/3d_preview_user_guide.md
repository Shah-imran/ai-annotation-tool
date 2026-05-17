# 3D Volume Preview — User Guide

This guide walks you through using the 3D preview when annotating volumetric
scans. It assumes you already have the tool installed and running.

If you're maintaining the codebase, see
[`3d_preview_technical.md`](./3d_preview_technical.md) instead.

---

## 1. What the 3D preview is for

The 3D preview lets you see your whole scan as a single 3D object while you
annotate. It's not the canvas you draw on — that's still the 2D slice
viewer on the left. The 3D view is there to help you:

- **Understand where you are in the scan.** A highlighted plane shows the
  current Z slice, so you always know where the 2D view sits inside the
  volume.
- **Find features fast.** Spot a small void, bump, or crack in 3D, then
  jump the 2D viewer to that slice and annotate.
- **Quality‑check your labels.** Toggle the mask overlay to see your
  annotated voxels as colored points sitting on the volume.

---

## 2. Switching into 3D mode

1. Launch the app.
2. At the top of the window, just under the menubar, you'll see two tabs:

   ```
   ┌───────────────────────┬────────────────────┐
   │  2D Bounding Boxes    │   3D Volume        │
   └───────────────────────┴────────────────────┘
   ```

3. Click **"3D Volume"**.

When you switch into 3D mode, the app quietly starts up the 3D preview
helper in the background. You don't see anything happen — that's
intentional. By the time you click "Start Preview" later, the helper is
already loaded and warm, so the first preview comes up faster.

---

## 3. Loading a scan

1. On the right‑side control panel, click **"Load Scan Folder…"**.
2. Pick the folder containing your TIFF stack (and optional label/segmentation files).
3. The 2D slice viewer fills in immediately. The right panel's
   **"3D Preview"** section shows: *"Loaded — click Start Preview"*.

The 3D view itself does **not** build automatically. Scans are big, and
auto‑building every time would waste your time on previews you don't
need. You decide when to build.

---

## 4. The two preview modes

In the **"3D Preview"** section of the right panel, the **"Mode"**
dropdown offers two choices:

### Isosurface (opaque, lit)

Best for: **seeing the shape and surface detail** of your sample.

- Renders the dense material as a solid, lit surface (think clay sculpture).
- Studio‑style three‑point lighting plus ambient occlusion shading make
  small voids, bumps, and crevices visible by darkening the corners.
- One color (neutral gray) so you focus on shape, not intensity.

### Point cloud

Best for: **fast preview, large scans, X‑ray‑style transparency**.

- Renders bright voxels as glowing dots in space.
- You can see through the volume — useful when something is hidden
  inside.
- Much cheaper to build than a mesh, so it's the right pick when you're
  scrolling around exploring or when your scan is huge.

You can change mode anytime. If a build is in progress, the panel
disables most controls until it finishes — just wait or hit Cancel.

---

## 5. Building your first 3D preview

1. Pick a **Mode** (see above).
2. (Optional) Adjust **Z stride** and **XY stride** under "Sampling":
   - **Stride 1** = use every slice / every pixel. Best quality, most
     RAM and CPU.
   - **Stride 2–4** = much faster, mild quality loss. Good for first‑pass
     exploration.
   - **Native resolution** checkbox forces stride 1×1×1 regardless.
3. Click **"Start Preview"**.
4. The status box shows progress in real time:
   - *"Loading slice stack…"*
   - *"Slice stack ready — preparing 3D display…"*
   - *"Mesh build (CPU thread) → GPU draw (chunked)."*
   - Finally: *"Isosurface (opaque) ready · Stride 2 · …"*

The 3D window will pop up on its own when you have an active preview.
You can hide it any time and reopen with **"Show 3D Window"** /
**"Hide 3D Window"**.

> **Tip:** if the main app feels sluggish during very large native
> builds, that's actually the preview helper using your CPU — the main
> annotation window stays responsive because the heavy work runs in a
> separate process.

---

## 6. Navigating the 3D view

The 3D window is a standard PyVista orbit view.

| Action | Mouse / key |
|---|---|
| Orbit | Left‑drag |
| Zoom | Mouse wheel |
| Pan | Middle‑drag, or Shift + Left‑drag |
| Reset view | Press **Home**, or click "Reset Orientation" in the panel |
| Move the 2D slice indicator | Scroll the 2D viewer's slider; the 3D plane follows |

There's also a **"Reset Orientation"** button on the right panel that
does the same thing as the Home key.

### The current slice plane

The blue translucent rectangle inside the 3D view is the slice you're
currently looking at in the 2D viewer. When you scrub the 2D slice
slider, the plane moves in 3D too — so you always know which Z you're
annotating.

---

## 7. The brightness slider (new)

The 3D preview window has a thin strip at the bottom:

```
Brightness  ────●──────────  100%   [Reset]
```

What it does:

- Slides every light in the 3D scene up or down in intensity.
- Range 10% (very dark) to 250% (very bright).
- 100% is the default. Click **Reset** to snap back.

When is this useful?

- You're using **Isosurface (opaque, lit)** and the inside of a void looks
  too dark to read. Boost to ~140% to brighten the rim lights.
- The default is too punchy for a particular sample. Drop to ~70% for a
  softer, more cinematic look.
- You want a flat, almost X‑ray look on a point cloud. Raise above 150%
  and the dots glow against the dark background.

The slider takes effect **instantly** — no rebuild, no waiting. It
doesn't change your data, only how it's lit.

> **Note:** the brightness setting is per‑session. It resets to 100% when
> you reopen the app. If you find yourself always nudging it the same
> way, mention it and we'll add a default.

---

## 8. Display Brightness & Contrast (2D — and what it does to the preview)

Below the navigation section on the right panel you'll see:

```
Display Brightness & Contrast
   Brightness (midpoint)  ────●───────────
   Contrast width         ──●─────────────
   [Reset Display]
```

This is the same control medical viewers call **Window / Level**:

- **Brightness (midpoint)** = the intensity that ends up as mid‑gray
  on screen. Slide right to brighten the image.
- **Contrast width** = how wide a range of intensities gets spread across
  the gray scale. Smaller width = more contrast, more punch. Larger
  width = softer, flatter look.

Two important things:

1. **It changes the 2D slice viewer immediately** so you can see exactly
   what's happening as you drag.
2. **It also changes what the 3D preview will look like next time you
   rebuild.** The 3D preview converts your raw scan to grayscale using
   the same brightness/contrast you've set. So if your scan looks washed
   out in 2D, your isosurface will too — adjust here first, then hit
   *Start Preview*.

**Reset Display** restores the auto‑picked default (similar to how a
TIFF viewer auto‑contrasts on open).

---

## 9. Typical annotation flow

A good rhythm for annotating with the 3D preview running:

1. **Load** the scan.
2. Click **"3D Volume"** if you weren't already there.
3. **Adjust 2D brightness/contrast** until features are clearly visible
   in the slice viewer.
4. Pick **Mode = Point cloud** with **Z stride = 2, XY stride = 2** and
   hit **Start Preview** — this is fast and gives you a rough overview.
5. Orbit the 3D view, find the area you want to label.
6. Note which Z range matters. Scrub the 2D viewer there.
7. (Optional) Switch to **Isosurface (opaque, lit)**, click **Start
   Preview** again for the detailed shape.
8. (Optional) Crank the **Brightness** slider in the 3D window to peek
   inside dark cavities.
9. Annotate in the 2D viewer. The 3D plane indicator follows you.
10. Toggle **"Show Mask Overlay"** to see your labels in 3D as colored
    dots layered on top of the gray volume. Spot any misses — go fix
    them in 2D.
11. **Save Labels**. Repeat.

---

## 10. Performance tips

- **Use strides liberally.** Native resolution is gorgeous but most
  decisions don't need it. Stride 2 in Z and XY is roughly an 8× speedup
  for a barely‑perceptible loss on slice‑plane features.
- **Point cloud first, isosurface second.** A point cloud build is
  multiples faster than a mesh; use it to navigate, then upgrade.
- **Hide the 3D window** when you're not looking at it. The build
  process keeps running on its own; hiding only changes whether you see
  it. But on Intel iGPUs, having the 3D window visible does cost a small
  amount of GPU time per frame.
- **Don't fight a slow build.** If the status text says it's working,
  it's working — in another process. Your annotation UI stays
  responsive. Take advantage of that and keep annotating in 2D while
  the 3D preview catches up.

---

## 11. Keyboard reference

| In | Key | Action |
|---|---|---|
| Main window | Tab through the 2D/3D tab strip | Switch mode |
| 2D viewer | `Ctrl` + mouse wheel | Zoom in/out |
| 2D viewer | Middle‑mouse drag | Pan |
| 2D viewer | `Home` | Reset zoom to fit |
| 3D window | Left‑drag | Orbit |
| 3D window | Wheel | Zoom |
| 3D window | Middle‑drag / `Shift` + drag | Pan |
| 3D window | `Home` | Reset 3D camera orientation |

---

## 12. Troubleshooting

### "Start Preview" is grayed out

A build is already running. Either wait, click **Cancel**, or — if the
button stays grayed for more than ~30 s with no progress text — the
3D helper may have crashed. Switching to 2D mode and back to 3D mode
will reset everything.

### The 3D window won't open

Click **"Show 3D Window"** on the right panel. If it still doesn't
appear, check whether anti‑virus or sandboxing on your machine is
blocking the helper process. The status box should show an error in
that case.

### The 3D preview looks too dark / too bright

Use the **Brightness slider at the bottom of the 3D window**. If that
isn't enough, adjust **Display Brightness & Contrast** on the right
panel and hit **Start Preview** again — the underlying data mapping
changes there.

### My voids look filled in

Increase **Contrast width** to *decrease* contrast, then hit **Start
Preview** again. Counter‑intuitive, but voids show up best when the
dense material isn't washed out into pure white. Alternatively, try the
point‑cloud mode — voids appear as empty space between glowing dots.

### "No surface at threshold" message in the 3D view

Your isosurface threshold doesn't match anything in this scan. Adjust
the **Brightness & Contrast** sliders (the 3D preview uses them to map
intensities) and rebuild. The point‑cloud mode is also a good fallback
because it doesn't rely on a single threshold.

---

## 13. A note on what's happening behind the scenes

When you click **Start Preview**:

1. The right panel collects every setting and packages it for the
   helper process.
2. A separate Python process (started in the background when you
   entered 3D mode) does the heavy lifting: reading TIFFs,
   downsampling, building meshes, and rendering them with VTK.
3. As it works, it sends back status updates that you see in the panel.
4. The finished 3D model lives in that helper process. You see it
   through the 3D window, which is also part of the helper.

This is why your annotation UI doesn't freeze even on huge scans — the
expensive work happens *next to* the main app, not *inside* it.
