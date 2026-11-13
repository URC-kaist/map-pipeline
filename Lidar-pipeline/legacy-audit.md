# Verification of the existing lidar pipeline

Reviewed 2026-11-13 at local `~/lidar` commit
`2489b0ef20da5f55644d5cef0f751ea36401fa13` (exact observed hash is in
[source-state evidence](evidence/legacy-source-state.json)). The configured
remote is `https://github.com/URC-kaist/lidar.git`. This audit did not modify it.

The user's planned successor is `URC-mr2/cartographer`; repository creation,
namespace selection, publication and retirement of the old repository are later
work. No remote was created or changed here.

## What was checked

| Stage | Observed implementation | Consequence for the replacement |
| --- | --- | --- |
| Point cloud → DEM | PDAL reads `input.laz`, retains classifications 1–2, and averages elevation at 0.4 **source CRS units** | Class 1 is unclassified, not guaranteed bare earth. New optional point-cloud path explicitly uses ground class 2 and an explicit projected metre CRS. Downloaded DEMs bypass this stage. |
| Fill holes | `fill.py` hardcodes `raw_mean.tif` and `fill_mean.tif`, calls Rasterio fillnodata | No bounded-hole selection or distinction between holes and absent coverage. New pipeline preserves unknown terrain; no automatic filling. |
| Reproject | Current shell script warps first to EPSG:4326, then to bare `+proj=topocentric` | Tiny-raster reproduction succeeds at the first warp and fails at the second, with mismatched PROJ units. The current documented end-to-end procedure cannot complete here. |
| Historical projection | Saved logs ran AEQD at 0.4/0.2 m; they predate the current ENU change | Those logs demonstrate an earlier pipeline, not success of the current script. New AEQD example is explicit and tested. Default keeps the source UTM grid. |
| Crop | Shell script crops around raster array center | This is not necessarily the configured datum. New configs specify bounds in the target CRS; local origin comes from actual bounds and anchor. |
| Slope | Current `filter.py` computes resolution-scaled Horn derivatives | README still describes Prewitt. New magnitudes match the legacy Horn interior; signed derivatives use explicit east/north conventions. Legacy convolution reverses the east sign. |
| Normalization | Legacy magnitude emits 255 at ≥45°; angle emits 0–254 at 0–45° | README's clamp descriptions are inconsistent. New previews saturate at 254 for magnitude/angle; Nav2 costs have their own documented encoding. |
| Missing terrain | Height preview replaces NaN with minimum elevation; slope images do not retain a validity mask | Some missing values become apparent flat/low terrain or numeric image values. New 3×3 slope validity and explicit unknown cost prevent that ambiguity. |
| Map metadata | Current `filter.py` does not emit YAML or the Gazebo block shown in old logs | New pipeline always emits resolution, lower-left origin, coordinate frame, corners, cost encoding and a Nav2 YAML. |
| Nav2 example in mr2-stack | `map0p4.yaml` uses `occupied_thresh: 1.63662`, `free_thresh: 1.0`, scale mode | These thresholds cannot express the intended occupied cells from an opaque 0–1 grayscale fraction. New raw-mode image contains 0–100 costs and 255 unknown; thresholds are valid but unused in raw mode. |
| Simulation mesh | Old scripts subtract minimum Z, center mesh independent of the actual map origin, fill missing values at minimum height, and may simplify twice | New mesh export places sampled pixel centers in the same local projected frame as the map; records Z offset; omits faces crossing unknown terrain. Deterministic grid sampling replaces optional simplification libraries. |
| Texture | NAIP downloader requests one image through a live USGS service; OBJ uses that image as a texture | New optional export uses the downloaded georeferenced RGB TIFF, warped to the DEM CRS and extent. Network access is unnecessary. Dashboard XYZ tiles remain a separate workflow. |
| Dependencies | Current machine has GDAL, NumPy, SciPy, Pillow and PDAL; lacks Rasterio, trimesh, fast_simplification and pyproj in `/usr/bin/python3` | Old scripts are not currently runnable unmodified even after projection repair. New core uses GDAL + NumPy, with Pillow for checks; optional mesh export needs no external mesh library. |

## Projection and map-frame findings

[Projection probe](evidence/legacy-projection-probe.json) records the commands,
exit codes and error output. `topocentric` accepts geocentric Cartesian XYZ;
geographic input requires a preceding Cartesian conversion. A bare topocentric
CRS must not be substituted for a tested 2D raster projection. See the official
[PROJ definition](https://proj.org/en/stable/operations/conversions/topocentric.html).

The new default uses EPSG:6341 and subtracts a configured anchor in that same
projection to define local map coordinates. This retains UTM grid orientation;
it is **not ENU**. Local ROS configurations mention UTM and do not set
`use_local_cartesian`; this does not establish the currently running robot's
projection, datum, grid-convergence compensation, heading, or TF. A real deployment
must establish those before loading the map.

The default anchor reproduces the **numbers and NAD83(2011) label** recorded in
`mr2-stack/.../maps/lidar_enu_4km_metadata.json`. This is a convenient explicit
test anchor, not proof that this new UTM map is equivalent to the old product
named ENU. The new dataset covers eastward from that anchor rather than a square
centered on it.

The old raster's compound CRS declares NAVD88 height; the new downloaded DEM's
vertical datum is not declared in its inspected TIFF metadata. The replacement
explicitly preserves elevation values and does not perform a vertical datum
transformation. Similar spot elevations do not establish a shared vertical datum
or source acquisition.

## Evidence and limits

- [Legacy source identities and clean status](evidence/legacy-source-state.json).
- [Original LAZ metadata](evidence/legacy-laz-metadata.json).
- [Current projection failure](evidence/legacy-projection-probe.json).
- [Analytic and integration checks](evidence/terrain-tests.log).
- [New real-data checks](evidence/real-data-verification.json).
- [Native Nav2 decode](evidence/native-nav2.json): installed Humble library, no
  ROS node, service, robot or simulation launch.

The earlier log/extents/elevation comparison remains in the parent README.
No complete old pipeline rerun is claimed: its current projection fails, some
Python dependencies are absent, and old logs describe different source crops.
Source reading identified the optional mesh issues; old mesh creation and its
download service were not exercised. New optional mesh creation is separately
tested on synthetic terrain and the new AEQD example.

Raw map behavior was checked against the installed library and the official
[Humble map I/O source](https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_map_server/src/map_io.cpp).
The generated YAML and PNG are a matched pair. Existing `map_cropper.cpp`
hardcodes a scale-mode configuration and a different metadata schema; this new
output is not a drop-in replacement for that consumer. Integration must retain
the raw encoding and mask semantics. Whether intermediate costs survive the
static layer also depends on its `trinary_costmap` setting.
