# Reproducible terrain and navigation maps

This is the working replacement for `~/lidar`'s terrain-generation procedure,
within **URC-kaist/map-pipeline**. It accepts an elevation GeoTIFF or
an explicitly configured ground-class point cloud, and generates terrain
features, a Nav2 cost map, metadata and optional simulation meshes. All
processing uses local files and runs offline.

The original implementation and its discrepancies are recorded in
[legacy-audit.md](legacy-audit.md). The original repository remains unchanged.
This is a validated local setup; RGB dashboard tile generation, rover-frame
alignment, final project cleanup and GitHub publication remain later work.

## Files and dependencies

```text
Lidar-pipeline/
├── README.md
├── legacy-audit.md
├── pipeline.py             # DEM/point cloud → features → Nav2 map
├── export_mesh.py          # Optional OBJ/STL and local RGB texture
├── verify.py               # Analytic, mask, geometry and integration checks
├── check_nav2.py           # Optional native Nav2 library roundtrip
├── check_nav2.cpp
├── config/
│   ├── mdrs-east.json       # Full 4 × 5 km UTM region, 0.5 m cells
│   └── legacy-aeqd.json     # Datum-centered 1 km AEQD example, 0.4 m cells
├── evidence/               # Audit and verification records
└── output/                 # Rebuildable results, ignored by Git
```

Use **`/usr/bin/python3`**, with GDAL Python bindings and NumPy. Tests also use
Pillow and SciPy (the latter for comparison with the old Horn function). Mesh
export uses the same GDAL/NumPy dependencies. PDAL is needed only for LAS/LAZ.
The optional native loader check requires installed ROS Humble Nav2 headers and
libraries and `g++`; it never starts ROS nodes.

On Ubuntu, the corresponding core/check packages are `gdal-bin`, `python3-gdal`,
`python3-numpy`, `python3-pil`, and `python3-scipy`; `pdal` is optional. No new
packages were installed for this setup. Observed runtime versions are captured
in each result's manifest: GDAL 3.4.1, PROJ 8.2.1, NumPy 1.24.4, Python 3.10.
Do not install an arbitrary GDAL pip wheel over the system bindings. Another
environment must pair its GDAL Python bindings with its GDAL library.

## Run with the downloaded DEMs

From `map-pipeline-testing/`, first build the source mosaic if absent:

```bash
/usr/bin/python3 mosaic_dem.py
```

Then, from this `Lidar-pipeline/` directory:

```bash
/usr/bin/python3 pipeline.py --config config/mdrs-east.json --output output/mdrs-east
```

The output directory must **not already exist**. To repeat a run, choose a new
name, such as `output/mdrs-east-repeat`. Inputs are never overwritten. Results
are built in a temporary sibling directory and appear at the requested path
only after a successful run. An unsuccessful run removes its temporary products.

Config input paths resolve relative to the config file, independent of the
shell's working directory. The default input is the stitched bare-earth DEM in
`../Lidar/`; the source archives and provenance stay there. No interpolation of
missing coverage is performed.

## Coordinate and processing contract

1. Read one projected, metre-based elevation band. Respect its NoData value.
   Elevations must be metres. The config explicitly records the vertical datum,
   including `unknown` when the source does not establish it.
2. Warp directly to the chosen projected CRS, explicit outer bounds and integer
   pixel dimensions. No intermediate longitude/latitude raster is introduced.
   Configured resampling is explicit; the default bilinear operation on the
   unchanged UTM grid preserves the original samples exactly. Reprojected or
   resampled outputs can differ and do not gain source detail.
3. Read rows with a one-cell halo and compute **Horn** east/north derivatives,
   slope magnitude (rise/run), and slope angle in degrees. A missing sample
   anywhere in a 3×3 neighborhood invalidates that slope. The outermost cells
   likewise have no complete neighborhood and remain unknown.
4. Generate diagnostic images and a separate navigation cost encoding. NoData
   is represented explicitly, rather than normalized into apparent low terrain.
5. Record anchor, actual grid, geographic corners, elevation range, cell counts,
   settings, versions and SHA-256 hashes. Preserve the exact executed source as
   `pipeline_source.py` in each new result.

The default target is **NAD83(2011) / UTM zone 12N, EPSG:6341**. It retains the
native source grid and rectangle E=518000–522000, N=4248000–4253000 m. Its test
anchor is latitude 38.4025461391511, longitude -110.793850513327 in EPSG:6318,
which projects to approximately E=518000, N=4250500 m.

**Local x/y = target projected x/y − projected anchor.** There is no rotation.
The Nav2 origin is the lower-left outer corner in those local coordinates,
approximately `[0, -2500, 0]` for the default. Pixel centers are offset by half
a cell; PNG/TIFF rows run north to south and Nav2 reverses them on loading.
The GeoTIFFs retain their full projected coordinates, not the local offset.

UTM grid axes are not a true ENU tangent plane. The geographic anchor label,
UTM grid convergence, heading and ROS transform must be reconciled with the
actual robot configuration before deployment. The old bare `topocentric` warp
is deliberately not reproduced as if it worked. No vertical datum conversion
is applied: source heights remain source heights. PROJ network access is
disabled during processing, so any required transformation grids must be local.

## Outputs and encoding

| Output | Meaning |
| --- | --- |
| `dem.tif` | Float32, original elevation units (metres), target projected CRS; -9999 unknown |
| `slope_magnitude.tif` | Float32 rise/run; -9999 where a full neighborhood is unavailable |
| `slope_degrees.tif` | Float32 arctangent slope in degrees; -9999 unknown |
| `validity.tif` | Byte 255 for valid slope/cost, 0 for unknown; georeferenced |
| `heightmap_norm.png` | Elevation min/max → 0–255; transparent where DEM is unknown; constant elevation maps to 0 |
| `slope_x_norm.png`, `slope_y_norm.png` | East/north signed derivative -1…1 → 0…255, clipped; transparent when invalid |
| `slope_length_norm.png` | Rise/run 0…1 → 0…254, clipped; transparent when invalid |
| `slope.png` | Angle 0…45° → 0…254, clipped; transparent when invalid |
| `occupancy.png`, `map.yaml` | Matched Nav2 **raw-mode** cost image and loading configuration |
| `metadata.json` | CRS WKT, anchor, local frame, lower-left origin, outer corners, units, counts and encoding |
| `config.json`, `pipeline_source.py`, `manifest.json` | Exact configuration and executed source; input/output checksums and dependency versions |

The navigation cost is **round(100 × clamp(tan(slope) / tan(full-cost angle),
0, 1))**, with the full-cost angle configured as 45° in both examples. Thus 0
is flat/free, 100 is full cost, and **255 is unknown**. This is a terrain slope
cost, not an observed obstacle probability or a validated rover safety limit.
It omits vegetation, rocks below source resolution and other live hazards.

Raw mode reads image bytes 0–100 as costs and bytes above 100 as unknown; the
YAML's valid threshold fields are unused in that mode. Do not load this PNG
through the old scale-mode YAML or the existing cropper's hardcoded scale
settings. To use graded costs in a Nav2 static layer, also review its
`trinary_costmap` policy. The generated metadata is the new documented schema,
not the older `map_cropper.cpp` schema. No consumer code was changed here.

The previews have alpha; use the GeoTIFFs and mask for computation. PNGs alone
do not carry the map projection. Cropping, shifting or resizing a PNG without
updating its YAML/metadata destroys registration.

## AEQD example and point-cloud input

To exercise an equivalent of the historical projection/crop workflow:

```bash
/usr/bin/python3 pipeline.py --config config/legacy-aeqd.json --output output/legacy-aeqd
```

This uses the old script's WGS84 origin, 38.406739, -110.791394, at 0.4 m/cell.
Unlike the old script, its crop is explicitly centered on that origin. The new
east-side DEM does not fully cover that square: the resulting unknown western
area is expected. It is not a reproduction of the old crop's exact extent,
source resolution or elevation range, nor is AEQD described as ENU.

LAS/LAZ is optional. In a separate config, point `input` to the actual file and
add the following block, **setting the CRS from that file's verified metadata**:

```json
"pointcloud": {
  "crs": "EPSG:6341",
  "resolution_m": 0.5,
  "ground_classes": [2]
}
```

The CRS above illustrates the new DEM's horizontal CRS; it is not an assertion
about the old `input.laz`. This option explicitly overrides the input LAS SRS,
so it must match the point coordinates. A synthetic ground/unclassified test
verifies that class 1 is excluded. PDAL outputs a mean-elevation raster; its
interpolation radius/default behavior also matters and the exact generated
PDAL specification and installed PDAL version are recorded. Further point-cloud
ingestion tuning needs the original acquisition metadata. The verified default
uses published bare-earth DEMs and has no PDAL interpolation stage.

## Optional simulation mesh and texture

For example, on the AEQD result:

```bash
/usr/bin/python3 export_mesh.py output/legacy-aeqd --output output/legacy-mesh --stride 25 --texture ../RGB/q3128_se_NAIP2024_RGB.tif
```

Outputs are OBJ+MTL+PNG, binary STL, and `mesh.json`. Omit `--texture` for an
untextured mesh; select `--format obj` or `--format stl` if only one is wanted.
The texture is warped from the local RGB TIFF to the DEM CRS and extent, capped
at 2048 pixels on its longest side. No live imagery service is used. The RGB
datum transformation is an executable example, not field-verified registration.

`--stride` is deterministic grid sampling, not adaptive mesh simplification.
Each face is accepted only when the entire full-resolution DEM quad it spans
is valid, so sampling cannot bridge a NoData hole. Mesh vertices use sampled
pixel-center local x/y, and Z minus the DEM's minimum valid elevation. Add the
recorded `z_offset_m` to restore source heights. The mesh already includes the
local x/y offset; do not recenter it again when placing it. No Gazebo SDF or
robot-frame placement is automatically asserted. The mesh is a surface, not a
closed watertight solid.

## Verification completed here

```bash
/usr/bin/python3 verify.py
/usr/bin/python3 check_nav2.py output/mdrs-east --report evidence/native-nav2.json
```

- Eight tests pass: analytic plane derivatives/cost, invalid-parameter rejection,
  full NoData neighborhoods/borders and YAML origin, synthetic reprojection,
  legacy Horn magnitude agreement, compound-CRS elevation preservation,
  ground-class point-cloud ingestion, and mesh
  orientation/coordinates/hole handling. Repeated small runs produce identical
  product hashes.
- Full real-data output is 8000 × 10000 at 0.5 m/cell. All 80 million output DEM
  samples, including NoData, match the stitched input exactly. Elevations span
  1322.45996–1447.70996 m.
- 7,015,755 navigation cells are unknown: original missing coverage plus the
  slope neighborhood and outer-edge exclusions.
- Installed Humble `libmap_io.so` decodes all 80 million map cells exactly,
  including unknown values and the north/south row reversal. No ROS node ran.
- The real AEQD example completed at 2500 × 2500, and optional OBJ/STL export
  with the local RGB texture completed with 14,200 faces.

Both full-size profiles were rebuilt; every shared output file matches its
initial-run SHA-256. Current source snapshots and every manifest output hash
were also checked. See [reproducibility evidence](evidence/reproducibility.json),
[audit evidence](evidence/) and each output manifest. `output/verification-baseline/`
retains the initial run for full-size reproducibility comparison; it is generated
evidence, not another source dataset. Outputs are intentionally not tracked by
the local `.gitignore`. Publishing source materials or selected generated maps
are kept outside normal source commits; see the root data policy.

No robot motion, runtime map loading, RGB dashboard XYZ generation, field
registration check or GitHub publication was performed in this task.
