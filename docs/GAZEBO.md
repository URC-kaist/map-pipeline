# DEM → textured Gazebo terrain

The optional workflow completes the previously missing import step:
**DEM → centered crop → textured OBJ + collision STL → model/world SDF → Gazebo**.
It uses local georeferenced RGB imagery. The tested simulator is **Gazebo
Fortress 6.18.0**, with OGRE2 rendering and DART physics. This is not a claim of
compatibility with every simulator version or rover model.

## Generate, view and capture

From the repository root, after the expanded terrain outputs and RGB inputs
exist:

```bash
/usr/bin/python3 Lidar-pipeline/export_gazebo.py \
  Lidar-pipeline/output/mdrs-expanded \
  --output Lidar-pipeline/output/mdrs-gazebo-relief \
  --texture RGB/q3128_se_NAIP2024_RGB.tif RGB/q3129_sw_NAIP2024_RGB.tif

ign sdf -k Lidar-pipeline/output/mdrs-gazebo-relief/world.sdf
ign gazebo -r Lidar-pipeline/output/mdrs-gazebo-relief/world.sdf
```

Generation uses the existing GDAL/NumPy environment. Viewing additionally needs
Gazebo Fortress, its Physics/SceneBroadcaster/Sensors plugins and working
OGRE2/OpenGL support. No ROS, Node, Fuel downloads or Internet is required. The
world includes its own light. A display is needed for the GUI; server-only
capture still needs a usable OpenGL context (tested with an X display and
software rendering).

The generated directory is relocatable. Keep `world.sdf`, `model/` and its
texture/material together; mesh URIs are relative. The standalone
`model/model.sdf` can also be included in another world using the frame mapping
below. Existing output directories are refused.

```bash
/usr/bin/python3 Lidar-pipeline/capture_gazebo.py \
  Lidar-pipeline/output/mdrs-gazebo-relief \
  --output Lidar-pipeline/output/mdrs-gazebo-relief-capture

/usr/bin/python3 Lidar-pipeline/verify_gazebo.py \
  Lidar-pipeline/output/mdrs-gazebo-relief \
  --output Lidar-pipeline/output/mdrs-gazebo-relief-collision
```

Capture verifies package hashes, creates a separate runtime SDF, and saves
960 × 720 camera frames, a log and `capture.json`. It runs 5,000 simulation
steps at a maximum 250 Hz update rate to allow rendering initialization, with
a default 90 s wall timeout. The default `--view detail` looks from southwest
at the highest point, at a lower oblique angle (about 20° down on this profile).
Closer framing, reduced ambient light and low directional lighting reveal
relief without changing elevations. `--view overview` gives a wider, higher view.

The world also includes **visual-only 20 m XYZ reference arms**: red X (grid
east), green Y (grid north), blue Z (up). The triad floats above the terrain so
all arms remain visible. It is a presentation aid, not a surveyed feature or
collidable object. Its pose, camera pose, FOV and target are recorded in
`gazebo.json`. The standalone terrain model contains no reference objects.

The collision smoke check runs without rendering: a sphere of radius 0.25 m
falls onto a relatively flat central part of the actual STL. Its final clearance
is compared with triangle-interpolated mesh height. It checks one location,
not complete collision coverage or rover dynamics.

Simulator checks need local transport sockets and normal Gazebo logging
permissions, which a restricted execution sandbox may need to allow. Gazebo
also maintains its usual logs outside the chosen output directory. Failures
retain diagnostic logs; retry with a new directory.

## Size and performance

Default **`--area-fraction .01`** means the centered one-hundredth of the original
map's area: each side is one-tenth as long. The 4 × 5.5 km profile becomes
**400 × 550 m**, with 800 × 1,100 original DEM samples. Geometry stays at
**one world unit per metre**, with no vertical exaggeration. For one-hundredth
of each side instead, use `--area-fraction .0001` (40 × 55 m on this profile).

Default **`--stride 8`** samples the 0.5 m DEM at 4 m spacing: 14,039 vertices
and 27,600 triangles. Textured OBJ with normals is about 2.6 MiB; STL about
1.3 MiB; texture about 1 MiB. `--stride 4` provides 2 m geometry at higher cost.
This is grid sampling, not error-bounded simplification; small obstacles and
slopes between samples can disappear.

The **2ⁿ + 1 samples per side** restriction concerns Gazebo's heightmap/Ogre
terrain representation ([official Gazebo Common documentation](https://gazebosim.org/api/common/5/classgz_1_1common_1_1Dem.html)).
Triangle meshes avoid that restriction, preserving the rectangular footprint
without stretching or padding. Texture dimensions need not be powers of two.
Explicit smooth OBJ normals are now exported: the prior normal-free OBJ failed
in this host's OGRE2 mesh conversion.

## Coordinate and texture contract

- Crop: **E 519800–520200, N 4250475–4251025 m**, EPSG:6341.
- World origin is the projected crop center; X follows grid east and Y grid
  north. Z subtracts the crop's minimum valid provider elevation.
- For this export: `E = world_x + 520000`, `N = world_y + 4250750`,
  `height = world_z + 1364.47998046875 m`. Exact offsets are in `gazebo.json`.
- Add approximately **(2000, 250) m** to world XY to reach the full terrain
  pipeline's local XY frame. This arithmetic mapping does not establish live
  robot TF. This world is grid-aligned, not true ENU; no spherical-coordinate
  configuration or surveyed field registration is asserted.
- Original EPSG:26912 RGB TIFFs are bilinearly warped to the crop's EPSG:6341
  extent. Multiple sources are supported; later valid sources win overlaps.
  UVs refer to DEM pixel centers, PNG north stays at the top, and V increases
  northward. There is no visual hand-alignment. Existing NAD83 datum-operation
  limitations still apply.
- Unknown DEM samples or incomplete RGB coverage cause rejection. Original
  full-resolution validity is checked before mesh sampling. Pixel-center
  vertices stop half a DEM cell inside the outer crop bounds.
- The static mesh is an open surface, not a watertight solid. Source heights
  are retained without vertical conversion; see [expanded coverage](EXPANDED-COVERAGE.md).

The package contains `dem.tif`, `gazebo.json`, `world.sdf`, and
`model/{model.sdf,model.config,terrain.obj,terrain.mtl,terrain.stl,texture.png,mesh.json}`.
Manifests record source hashes, bounds, metric offsets, sampling and asset hashes.
Full generated packages remain ignored by Git.

## Verification

On 2026-11-28 both SDF files passed `ign sdf -k`. Gazebo loaded the world and
produced six identical RGB-textured camera frames. A separate 6,000-step
collision check recorded probe poses; the sphere ended about **0.24954 m** above
the mesh, consistent with its 0.25 m radius. See
[simulator evidence](gazebo-verification.json).

Synthetic tests cover crop placement/scale, two adjacent georeferenced RGB
sources, normals, relative SDF asset references, overwrite refusal, missing
terrain/texture rejection and triangle height interpolation. `make test` runs
these without Gazebo; actual simulator checks remain optional and separate
from core CI.

The [preview documentation](images/README.md) identifies the real camera frame
and the smaller footprint marked in cyan on the overview maps. Source
[attribution and terms](SOURCES.md) apply to textures and renders. The code
license remains undecided.
