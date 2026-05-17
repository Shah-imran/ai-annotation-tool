# 3D Preview — Technical Implementation & Design Choices

This document covers everything behind the **3D Volume Preview** feature in the
annotation tool: how the pipeline is wired, why it lives in a child process,
what each stage does, and the trade‑offs taken at every layer. It is intended
for developers maintaining or extending the feature.

For an end‑user walkthrough, see [`3d_preview_user_guide.md`](./3d_preview_user_guide.md).

---

## 1. High‑level architecture

The 3D preview is a **multi‑process, multi‑threaded** subsystem. From the
parent app's perspective it looks like a single widget; in reality there are
two operating‑system processes and four logical threads of execution.

```
┌─────────────────────────  Parent process (main app)  ──────────────────────────┐
│                                                                                │
│  ┌────────────────┐   signals     ┌───────────────────────┐                    │
│  │  Volume        │  ───────────▶ │  VolumeController     │                    │
│  │  ControlPanel  │ ◀───────────  │  (orchestrates state) │                    │
│  └────────────────┘               └─────────┬─────────────┘                    │
│                                             │                                  │
│                                   make_preview_inputs(...)                     │
│                                             │                                  │
│                                             ▼                                  │
│                                ┌────────────────────────┐                      │
│                                │ PreviewProcessClient   │                      │
│                                │  - QLocalServer        │                      │
│                                │  - JSON-line IPC       │                      │
│                                │  - QProcess lifecycle  │                      │
│                                └───────────┬────────────┘                      │
│                                            │                                   │
└────────────────────────────────────────────┼───────────────────────────────────┘
                                             │  QLocalSocket  (newline JSON)
                                             ▼
┌─────────────────────────  Child process (preview)  ────────────────────────────┐
│                                                                                │
│  ┌────────────────────┐ ◀───── messages ─────┐    ┌──────────────────────┐    │
│  │  ChildIpcEndpoint  │                       │    │  ChildPreviewWindow  │    │
│  │  (dispatches IPC)  │ ─────── status ─────▶ │    │  (QMainWindow +      │    │
│  └────────┬───────────┘                       │    │   brightness slider) │    │
│           │                                   │    └────────┬─────────────┘    │
│           │ start_build / cancel / set_slice  │             │                  │
│           ▼                                                 ▼                  │
│  ┌────────────────────────────┐  worker (QThread)   ┌────────────────────┐    │
│  │ ChildPreviewCoordinator    │ ──────────────────▶ │ VolumePreviewWorker│    │
│  │ - generation tracker       │                     │ slice load + ds    │    │
│  │ - status formatter         │ ◀── result ─────── └────────────────────┘    │
│  └──────────────┬─────────────┘                                                │
│                 │  begin_set_preview(result)                                   │
│                 ▼                                                              │
│  ┌────────────────────────────┐  worker (QThread)   ┌────────────────────┐    │
│  │  VolumePreview3D widget    │ ──────────────────▶ │ VolumePreviewVTK   │    │
│  │  - owns QtInteractor       │                     │   Worker           │    │
│  │  - chunked GPU upload      │ ◀── payload ─────── │ contour + meshes   │    │
│  │  - lighting & SSAO         │                     └────────────────────┘    │
│  └────────────────────────────┘                                                │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

Three operating layers, in order of how a build flows through them:

| Stage | Process | Thread | Module |
|---|---|---|---|
| 1. UI input → params | Parent | UI | `views/volume_control_panel.py`, `controllers/volume_controller.py` |
| 2. IPC ship‑off | Parent | UI | `services/preview_ipc.py`, `services/preview_process_client.py` |
| 3. IPC receive & dispatch | Child | UI | `preview_process/ipc_endpoint.py` |
| 4. Slice load + downsample | Child | QThread (worker) | `services/volume_preview_worker.py`, `services/volume_preview_builder.py` |
| 5. Mesh / contour build | Child | QThread (worker) | `services/volume_preview_vtk_worker.py`, `services/volume_vtk_prepare.py` |
| 6. Chunked GPU attach + draw | Child | UI | `views/volume_preview_3d.py` (QtInteractor) |
| 7. Status / finished reply | Child | UI | `preview_process/child_coordinator.py` → IPC → parent |

---

## 2. Why a separate child process?

This is the single biggest architectural choice in the feature and is worth
understanding before changing anything.

### The problem

The preview pipeline does CPU‑heavy work in two stages:

1. **Slice loading + downsampling** — load *N* TIFFs from disk, apply
   window/level mapping, max‑pool to lower XY, stack into a `(Z′, H′, W′)`
   `uint8` cube.
2. **VTK mesh generation** — `pv.ImageData.contour(...)`, `clean()`,
   `triangulate()`, `compute_normals()`. Each step copies large `numpy`
   / `vtkPolyData` buffers.

Even when both run on a `QThread`:

- Python's GIL means the main thread doesn't get many CPU cycles during heavy
  pure‑Python sections, so paint events lag.
- VTK and PyVista call back into the same `QtInteractor` we created on the
  GUI thread. Several VTK operations end up touching OpenGL objects bound to
  the main thread context, which serialises with the rest of the UI.
- Peak RAM during contour + triangulate of large grids can spike several GB.
  On Windows, when that allocation crosses a working‑set ceiling the OS
  starts trimming pages and the main app feels frozen.

We tried (in order): pure threading, splitting the worker into "slice‑load
QThread" + "VTK QThread", carving the VTK upload into 16‑element chunks via
`QTimer`. Each helped a little, none fully eliminated the freeze on large
scans because the entire QApplication event loop still owned both the UI and
the OpenGL context.

### The solution

Move the entire preview pipeline into a **dedicated `QProcess`** that runs
`python -m annotation_tool.preview_process`. The two processes communicate
via a `QLocalServer`/`QLocalSocket` named pipe using newline‑delimited JSON.

Benefits:

- The OS schedules the two processes independently — the main app's
  event loop is never starved.
- Memory churn is isolated to the child. When a build finishes, the bulk
  `numpy` arrays and `vtkPolyData` only need to be reclaimed inside the
  child's heap; the parent's resident set stays flat.
- A crash in the child (e.g., a VTK error on a degenerate mesh) cannot
  bring down the user's annotation work. The parent detects the
  disconnect, clears its busy state, and offers to spawn again.
- The child window owns its own `QtInteractor`, so its OpenGL context is
  isolated from the main app's windows.

Costs paid:

- Slice data and labels can no longer be shared via Python objects. They
  are referenced by **file path** (TIFFs and the label memmap on disk),
  and the child re‑reads them itself. This keeps the IPC payload small
  and pure JSON.
- A few hundred ms of cold‑start cost the first time the child is needed.
  We hide this with **pre‑spawning** (§5).

---

## 3. Process lifecycle

### Spawning

`PreviewProcessClient` (parent) creates a `QLocalServer` with a unique socket
name (`annotool_3dpreview_<uuid>`) on construction. It does **not** start the
child until something asks it to.

The first time `ensure_started()` is called (typically from
`prewarm_preview()` after a scan loads, or lazily from `_send()` when a
message has nowhere to go yet), it does:

1. Build a `QProcess` whose program is `sys.executable` and whose arguments are
   `["-u", "-m", "annotation_tool.preview_process", "--socket", <name>]`.
2. **Inherit the parent's full environment** via
   `QProcessEnvironment.systemEnvironment()`. Critical: without this,
   `Path.home()` inside the child raises `RuntimeError: Could not determine
   home directory.` because Windows' `USERPROFILE`/`HOMEPATH` aren't passed
   through by default.
3. Set `PYTHONUNBUFFERED=1` so child `print()`s reach our terminal.
4. Hook `started`, `errorOccurred`, `finished` signals.
5. Call `QProcess.start()` — **without** `waitForStarted()`.

`waitForStarted()` blocks the parent's event loop for hundreds of
milliseconds. We removed it deliberately and instead track an
`_is_spawning` flag that flips on `start()` and clears on either the
`started` signal (success) or `errorOccurred` with `FailedToStart` (failure).
Any IPC messages issued while the child is still booting are buffered in
`_pending_messages` and flushed when the child sends its `READY` reply.

### Pre‑spawning

Cold‑starting `pyvista` + VTK + numpy + PIL in a subprocess takes 1.5–3 s.
That's bearable once per session but very obvious if it happens on the first
"Start Preview" click. We pay it ahead of time in two places:

- `MainController._on_annotation_mode_changed("3d")` calls
  `VolumeController.prewarm_preview()` so opening the 3D tab spawns the
  child in the background.
- `VolumeController.load_scan()` also calls `prewarm_preview()` so loading
  a scan pre‑warms even if the user starts in 2D mode and switches later.

The user sees no UI difference — `prewarm_preview()` is non‑blocking; the
child just sits idle, connected, until the first `START_PREVIEW`.

### Shutdown

The parent owns lifecycle:

- `PreviewProcessClient.shutdown()` sends `MSG_SHUTDOWN` and gives the child
  ~1.5 s to exit. If it doesn't, `terminate()` then `kill()`.
- The child's `closeEvent` on its window does **not** quit — it just hides
  and emits `user_closed` so the parent can toggle the show/hide button. The
  child only exits on `MSG_SHUTDOWN` or when the socket disconnects.
- If the child dies unexpectedly, `RemoteVolumePreview3D` (the parent‑side
  proxy) emits `render_finished` for the in‑flight generation so the panel
  drops its busy state and the user can retry.

---

## 4. IPC protocol

Defined in `annotation_tool/services/preview_ipc.py`. **Newline‑delimited
JSON** over a `QLocalSocket`.

```
{"type": "start_preview", "generation": 7, "params": {...}}\n
```

`JsonLineReader` buffers partial reads and splits on `\n`. A garbled line
becomes a `{"type": "log", "level": "error", ...}` message instead of
crashing the dispatcher.

### Parent → Child

| Type | Payload | Purpose |
|---|---|---|
| `hello` | — | wake the child, get a READY back |
| `start_preview` | `generation: int`, `params: dict` | begin a new build |
| `cancel` | — | abort the current build |
| `set_slice` | `z: int` | move the highlighted Z plane in 3D |
| `reset_view` | — | recenter the 3D camera |
| `clear` | — | drop the scene |
| `show_window` | — | show the child window |
| `hide_window` | — | hide it |
| `shutdown` | — | exit cleanly |

### Child → Parent

| Type | Payload | Purpose |
|---|---|---|
| `ready` | — | child is initialised and listening |
| `stage` | `text`, `generation` | status text update |
| `started` | `generation` | confirms a build has begun |
| `finished` | `generation`, `text` | build done; carries final summary |
| `failed` | `generation`, `text` | build failed; carries error message |
| `window_closed` | — | user clicked X on the child window |
| `log` | level, text | debug / error logging passthrough |
| `bye` | — | exiting |

### Generation numbers

Every preview build carries a monotonically increasing `generation: int`
assigned by the parent. The child echoes it on every reply. The parent's
proxy drops anything whose generation isn't the current one. This is how
we handle the "user changed mode while build was in flight" race: the old
build's `finished` / `failed` arrives, is ignored, and the new build's
generation is what gates UI state changes.

### Why JSON and not pickle / msgpack?

- **No code execution on receive.** Pickle would allow a crashed child to
  exfiltrate or execute arbitrary classes during unpickle.
- **Debuggable.** A misbehaving build can be diagnosed by piping the IPC
  through `Wireshark`/`procmon` or by dropping a `print` in
  `JsonLineReader.feed`.
- **Small payload.** The only large things — slice TIFFs and the label
  memmap — never cross the wire; they're paths.

---

## 5. The build pipeline (inside the child)

Triggered by `start_preview`. Coordinated by
`ChildPreviewCoordinator.start_build(generation, params)`.

### 5.1 Slice load + downsample — `VolumePreviewWorker` on a `QThread`

`services/volume_preview_worker.py` wraps `services/volume_preview_builder.build_preview`.
The worker is moved to a `QThread`, signals are wired before `start()`, the
thread is auto‑deleted via `deleteLater` connections. Cancellation flows
through a `request_cancel()` method that flips an internal `_should_cancel`
flag the builder polls on each slice.

Inside `build_preview`:

1. Decide effective `stride_zyx` (Z, Y, X). Either:
   - User‑specified strides from the panel, OR
   - `_auto_stride(...)` picks the smallest factor that fits the **target
     voxel budget** (e.g., 28 M voxels for `isosurface_lit`).
   - "Native resolution" overrides everything to `(1,1,1)`.
2. `build_downsampled_intensity` walks `slice_paths` one at a time:
   - `load_slice_tiff` → 2D `uint16`/`uint8` slice.
   - `slice_to_preview_u8` applies window/level (or auto‑contrast) to map
     to `uint8`.
   - `_max_pool_2d` for XY downsample (preserves bright pixels; using
     `[::sy, ::sx]` decimation lost thin features in early versions).
3. Result is a contiguous `(Z′, H′, W′)` `uint8` array — bounded RAM and
   GPU‑friendly.
4. For `point_cloud` mode, threshold the intensity cube and emit
   `(N, 3)` `xyz_points` + `(N,)` scalars, capped at
   `point_max_points`.
5. For `isosurface_lit`, pick the iso level (fixed `128.0` — empirically
   the best default for our recon‑style scans; the older `isosurface`
   mode used the 55th percentile of nonzero voxels).
6. If labels exist on disk, open them as a `numpy.memmap` of shape
   `label_shape` and extract sparse non‑zero points via
   `build_mask_point_cloud`. The memmap is opened on the worker thread —
   no Qt — and never crosses the IPC.

Output: a `VolumePreviewResult` dataclass.

### 5.2 Mesh / contour build — `VolumePreviewVTKWorker` on a second `QThread`

`services/volume_preview_vtk_worker.py` wraps
`services/volume_vtk_prepare.build_preview_payload`. We use **a second
worker thread** because mesh prep is independently expensive and we want the
child's UI thread free to keep painting the spinner while the mesh is being
built.

`build_preview_payload` produces a `PreviewVTKPayload`:

```python
@dataclass
class PreviewVTKPayload:
    result: VolumePreviewResult
    current_z: int
    generation: int
    primary: list[(kind, data, kwargs)]
    mask: list[(kind, data, kwargs)]
    volume_fallback: list[(kind, data, kwargs)] | None
```

Each entry is one of `"text"`, `"mesh"`, or `"volume"` — a tiny tagged‑union
the GPU stage knows how to attach.

#### Mode‑specific work

- `isosurface_lit` → single `grid.contour([iso])` → `clean()` →
  `triangulate()` → `compute_normals()`. Mesh kwargs are tuned for
  opaque, lit shading: `color="#dcdcdc"`, `smooth_shading=True`,
  ambient/diffuse/specular tuned, `_detail_lit=True` flag.
- `isosurface` (legacy, layered) → multiple percentiles 32–82, varying
  opacity per layer for X‑ray look.
- `solid` → `pv.add_volume(grid, blending="composite", shade=True)` with a
  custom opacity LUT that emphasises bone/material brightness. Falls back
  to layered isosurfaces if the GPU raycaster is unavailable.
- `mip` → `pv.add_volume(..., blending="maximum", shade=False)`. Same
  fallback to layered isosurfaces.
- `point_cloud` → straight `pv.PolyData(points)` + scalars.

The legacy `solid`, `mip`, and `isosurface` modes still exist in the
builder code because removing them risked breaking saved settings. The
panel only exposes `isosurface_lit` and `point_cloud` to keep the UX
focused.

#### Memory hygiene

- `_adaptive_isosurface_layer_count(vol)` drops from 5 → 2 layers for
  very large grids so peak `contour + triangulate` RAM stays bounded.
- `gc.collect()` is called between layers — generationally large allocs
  benefit from explicit collection on Windows.
- All large arrays live only on the worker thread's stack; the payload
  contains references to `vtkPolyData`, which holds the memory until the
  main thread attaches it. The bridge handoff is therefore zero‑copy.

### 5.3 GPU attach + render — `VolumePreview3D` on the child UI thread

`views/volume_preview_3d.py` is reused inside the child. Its
`begin_set_preview(result, current_z, generation)` accepts the payload and:

1. Stores the result, clears prior actors.
2. Kicks off the VTK worker via `start_vtk_prepare_thread`.
3. On worker `finished(payload)`, enqueues every command into
   `_apply_queue` and starts the **chunk timer**: every 0 ms (i.e., next
   event‑loop iteration) it attaches up to N actors and re‑renders.
4. After the last chunk, calls `_reset_camera_to_data()` and emits
   `render_finished(generation)`.

Why chunked? A single `add_mesh` of a 2M‑triangle surface takes long
enough to stall paint events for ~100 ms. Spreading attaches across
several event‑loop turns keeps the child window's spinner animating and
makes cancellation responsive.

#### Lighting & SSAO

`_enable_detail_lighting()` (called for `isosurface_lit`):

1. `remove_all_lights()` to clear VTK's default headlight.
2. Add three `pyvista.Light` instances:
   - **Key**: from the upper‑right‑front, intensity 0.95, neutral white.
   - **Fill**: from the upper‑left, intensity 0.45, slightly cool tint
     (`#cfd6e0`) to push the shadow side warmer by contrast.
   - **Rim**: from below‑back, intensity 0.35, warm tint (`#ffd9b3`) to
     pop edges of bumps and void rims.
3. `enable_ssao(radius=12.0, bias=0.01, kernel_size=64, blur=True)` —
   screen‑space ambient occlusion darkens crevices and the insides of
   small voids, dramatically improving depth perception of pinhole‑sized
   features inside dense material.
4. `enable_eye_dome_lighting()` adds depth contour cues that work
   especially well on point clouds and edge‑heavy meshes.
5. `enable_anti_aliasing("ssaa")` — supersampled AA for clean silhouettes.

Each step is wrapped in `try/except` because not all VTK builds ship the
SSAO/EDL/SSAA support, and we want the preview to keep working on the
fallback.

#### Brightness slider (new)

The child window owns a `QSlider` (10–250%) below the 3D view.
`VolumePreview3D.set_brightness(factor)` scales every renderer light by
`factor`, relative to a **snapshot** of light intensities taken when the
lighting setup was installed. The snapshot is refreshed in three places:

- On widget construction (default headlight).
- After `_enable_detail_lighting()` adds key/fill/rim.
- After `clear()` (in case `pv.Plotter.clear()` reset the lighting).

`_apply_brightness_factor()` walks the renderer's light collection and
calls `light.SetIntensity(base[i] * factor)` for each. Repeated slider
moves rescale against the snapshot, not the previous value, so dragging
never compounds.

The slider lives in the child window — **not** the main app — for two
reasons:

1. It mutates OpenGL/VTK state that already lives in the child. No reason
   to round‑trip the change through IPC and add latency.
2. Per‑user preference is naturally session‑scoped; we don't persist it.

### 5.4 Status reply

`ChildPreviewCoordinator._format_status(result)` composes a multi‑line
human summary (mode, stride, slice count, downsampled XY size, RAM
estimate for native, point count). It goes back over IPC as
`{"type": "finished", "text": ..., "generation": ...}`. The parent's
panel displays it in the status box.

---

## 6. Parent‑side details

### `RemoteVolumePreview3D` (the headless proxy)

`views/volume_preview_3d.py` actually defines two classes used together:

- `VolumePreview3D` — the real widget (uses PyVista, owns a `QtInteractor`).
  In the child it's added to a `QVBoxLayout`. In the parent it's
  instantiated but **never added to any layout** — it's only a shape‑holder
  for compatibility.
- `RemoteVolumePreview3D` — the parent‑side proxy that the controller and
  panel talk to. It forwards calls (`begin_set_preview`, `set_brightness`
  isn't proxied because it lives in the child window) over IPC and emits
  `render_finished` whenever the child confirms a build is complete.

The proxy also implements `_clear_busy_for_active_generation()` — emits
`render_finished(current_gen)` on disconnect or spawn failure so the
panel never gets stuck with a grayed "Start Preview" button.

### `VolumeController`

`controllers/volume_controller.py` is the glue. It:

- Collects parameters from the panel, current scan, label memmap, and
  settings model and builds the IPC payload via
  `preview_ipc.make_preview_inputs(...)`.
- Bumps the generation counter and calls
  `_preview.begin_set_preview(result, current_z, generation)`.
- Subscribes to `_preview.busy_changed` (synthesised from `started` /
  `render_finished` / `failed` signals) and forwards busy state to the
  panel so it can disable controls during a build.

### `VolumeControlPanel`

`views/volume_control_panel.py` — the right‑side panel in 3D mode. Notable:

- The "Display Brightness & Contrast" group (renamed from the medical
  "Window / Level") holds two sliders: **Brightness** (window center) and
  **Contrast width** (window width). Tooltips keep the original W/L
  vocabulary for reference.
- The "Show / Hide 3D Window" pair lives here, **not** in a separate
  pane in the workspace. `set_preview_window_visible(bool)` toggles which
  of the two is shown.
- `set_preview_busy(bool)` disables most controls during a build so the
  user can't kick off a second one. The Cancel button is the exception.
- A `QStackedWidget` swaps between the mode‑specific knobs:
  - `isosurface_lit` page → a single label explaining there are no
    user‑tunable parameters for this mode (deliberately kept clean after
    the earlier experiment with threshold/color/smooth knobs was
    reverted — see Pending Tasks in the chat history).
  - `point_cloud` page → point size, auto/manual threshold.

---

## 7. Persistence

`models/settings_model.py` stores user preview preferences. Saved across
sessions:

- `volume_preview_mode` — last selected mode (`isosurface_lit` or
  `point_cloud`).
- `volume_preview_stride_z`, `volume_preview_stride_xy`,
  `volume_preview_native_resolution`.
- `volume_preview_show_mask`.
- `volume_preview_point_size`, `volume_preview_point_threshold_auto`,
  `volume_preview_point_threshold` — point‑cloud specific.

The brightness slider is **not** persisted because it's an in‑session
display tweak, not a content parameter. The 2D Brightness & Contrast
(W/L) state on the slice view *is* persisted via the existing W/L code
path.

---

## 8. Performance budget

Order‑of‑magnitude numbers for a "typical" scan (512 × 512 × 600 → ~157 M
uint16 voxels):

| Stage | Time | RAM (peak) | Notes |
|---|---|---|---|
| Slice load + downsample (stride 2/2/2) | 3–6 s | ~50 MB | I/O bound on HDD, CPU bound on SSD |
| Native (stride 1/1/1) | 12–20 s | ~150 MB | Single uint8 cube |
| `pv.ImageData.contour` | 1–3 s | +200–600 MB | One‑shot for `isosurface_lit` |
| `clean + triangulate + normals` | 0.5–1.5 s | brief +200 MB | |
| `add_mesh` chunked attach | 0.2–0.6 s | +50 MB GPU | Spread across 8–16 event‑loop turns |
| `enable_ssao + edl + ssaa` | <50 ms | negligible | Per‑frame cost rises a little |

The chunked attach is the only step that touches OpenGL on the child's UI
thread. Everything heavier runs on worker QThreads inside the child, so
the parent app's framerate stays flat.

---

## 9. Failure modes and how they're handled

| Failure | Detection | Recovery |
|---|---|---|
| Child won't start (`FailedToStart`) | `QProcess.errorOccurred` | `_is_spawning` cleared; proxy emits `render_finished`; user can retry |
| Child crashes mid‑build | socket `disconnected` signal | Proxy emits `render_finished(current_gen)`; panel un‑busies; `disconnected` signal also fires |
| User cancels | `MSG_CANCEL` | Worker polls cancel flag between slices; emits `failed` with "cancelled" text |
| VTK contour returns 0 points | `surface.n_points == 0` in `_build_isosurface_commands` | Try four fallback iso levels (40/60/90/120); if still empty, emit a text overlay |
| GPU raycaster unavailable (solid/mip) | `try_add_volume` returns False | `volume_fallback` (layered iso meshes) attached instead, with a banner |
| Old build finishes after a new one starts | `generation` mismatch | Coordinator returns early on stale generations |
| SSAO / EDL / SSAA unsupported | `try/except` around each | Silently fall back to flat lighting |

---

## 10. Extension points

- **Add a new render mode.** Touch the four spots: `volume_control_panel`
  combo + page, `_format_status` label, `volume_vtk_prepare` mode branch
  (new entry in `build_preview_payload`), `preview_quality` voxel/point
  budget. Don't forget to teach `child_coordinator._mode_label`.
- **New per‑mode knob.** Add the field to
  `VolumeControlPanel` (UI + signal), the settings model (persistence),
  `make_preview_inputs` (IPC plumbing), `ChildPreviewCoordinator.start_build`
  (extract from `params`), `VolumePreviewWorker.configure` (forward to
  builder), and finally consume it in `build_preview` / `build_preview_payload`.
  This is the path the (reverted) iso‑threshold/color/smooth knobs took.
- **In‑child UI controls.** Put them in `child_window.py` and call methods
  on `VolumePreview3D` directly — no IPC needed (the brightness slider is
  the canonical example). Only round‑trip through IPC for things the
  parent owns the state of, like which build to start.
- **Different IPC transport.** `JsonLineReader` is bytestream‑agnostic.
  Swapping `QLocalSocket` for a TCP socket would let the child run on a
  remote machine — useful future direction for GPU‑server setups.

---

## 11. Known limitations

- The child re‑imports the entire scientific stack on each spawn (~2 s).
  We can't share the warmed interpreter across sessions; future work
  could keep a daemon child alive across scan loads, but pre‑spawning
  handles the common case.
- Brightness is a multiplier on **all** lights, not a per‑light slider.
  Power users wanting cinematic control would want separate
  key/fill/rim sliders; not currently exposed.
- Cancellation latency is "between slices" for the loader and "between
  contour levels" for the mesh builder. Worst case ~1 s on huge grids.
- The legacy `solid` / `mip` / `isosurface` modes are still present in
  the builder and still respond if forced via settings, but are not
  exposed in the panel. They will be deleted in a future cleanup once
  we're confident no user has them in their saved settings.

---

## 12. Files to know

| File | Role |
|---|---|
| `controllers/volume_controller.py` | Top‑level orchestrator on parent side |
| `controllers/main_controller.py` | Mode switching, scan load, pre‑warm hook |
| `views/volume_control_panel.py` | Right‑side panel, settings widgets |
| `views/volume_preview_3d.py` | The 3D widget (in child) + parent proxy |
| `services/preview_ipc.py` | Wire format, payload builder |
| `services/preview_process_client.py` | Parent IPC client, `QProcess` lifecycle |
| `services/volume_preview_builder.py` | Slice → downsampled `uint8` cube + point cloud |
| `services/volume_vtk_prepare.py` | Cube → VTK meshes / volumes |
| `services/volume_preview_worker.py` | `QThread` wrapper around the builder |
| `services/volume_preview_vtk_worker.py` | `QThread` wrapper around the mesh prep |
| `services/preview_quality.py` | Quality level → voxel budget mapping |
| `preview_process/__main__.py` | Child process entrypoint |
| `preview_process/ipc_endpoint.py` | Child IPC dispatcher |
| `preview_process/child_coordinator.py` | Drives the build inside the child |
| `preview_process/child_window.py` | Child `QMainWindow` (includes brightness slider) |
