# Map pipeline testing

Workspace for recovering and validating both pipelines:

- RGB aerial imagery → offline dashboard tile map.
- LiDAR point cloud or bare-earth DEM → elevation/slope products → navigation occupancy map.

The intended successor project is **`URC-mr2/cartographer`**, replacing the old
lidar project with the finished, cleaned-up version of this workspace. The goal
is documented, reproducible map generation with explicit geographic alignment.
Final cleanup and GitHub publication are later steps; no remote repository or
push was created in this work.

The [new Lidar pipeline](Lidar-pipeline/README.md) now implements and tests the
terrain workflow, with a [verification of the original implementation](Lidar-pipeline/legacy-audit.md).
It includes explicit map bounds and frames, preserved unknown terrain, Nav2
raw-mode output, provenance manifests, and optional local-texture OBJ/STL export.
The RGB pipeline is implemented as described below; field alignment remains
to be validated separately.

The [RGB pipeline](RGB-pipeline/README.md) now crops the imagery to the DEM's
outer footprint, generates zoom 14–18 XYZ PNGs, and bundles an offline MapLibre
viewer plus Python server. The tested output has 1,983 tiles (about 141 MiB).
Projection arithmetic, tile placement, transparency, HTTP routes and offline
browser rendering/overzoom are checked; precise datum/rover registration remains
pending. The original dashboard has not been modified. The earlier
[research plan](RGB-pipeline/research-plan.md) remains as history.

Check geographic alignment between the products, including coordinate reference
systems, datum transformations, projection, pixel origins and indexing, extents,
and resolution. Different output projections may be appropriate for the two
consumers; alignment must be checked geographically rather than assumed from
matching pixel coordinates. Source-grid, synthetic-coordinate and native map
decoding checks now pass in `Lidar-pipeline/`; RGB/navigation field registration
remains unverified.

## Directory structure

```text
map-pipeline-testing/
├── README.md
├── mosaic_dem.py                # Reproduce mosaic and verification
├── RGB-pipeline/                # Cropped tiles, offline viewer and Python server
│   ├── README.md
│   ├── generate.py, serve.py, verify.py
│   ├── config/
│   ├── evidence/
│   └── output/                  # Rebuildable results, ignored by Git
├── Lidar-pipeline/              # Reproducible terrain/occupancy workflow
│   ├── README.md
│   ├── legacy-audit.md
│   ├── pipeline.py
│   ├── export_mesh.py
│   ├── verify.py
│   ├── config/
│   ├── evidence/
│   └── output/                  # Rebuildable results, ignored by Git
├── Lidar/
│   ├── 12SWH*.zip               # Eight original DEM archives
│   ├── 12SWH*.tif               # Eight extracted elevation rasters
│   ├── 12SWH*.tfw               # Eight extracted world files
│   ├── bare_earth_2018_0p5m.vrt # Georeferenced virtual mosaic
│   ├── bare_earth_2018_0p5m.tif # Standalone, losslessly compressed mosaic
│   └── mosaic-verification.json
└── RGB/
    ├── q3128_se_NAIP2024_RGB.zip
    ├── q3128_se_NAIP2024_RGB.tif
    └── q3128_se_NAIP2024_RGB.tfw
```

Paths below are relative to this workspace. Existing `~/lidar` is a separate
processing repository; it has not been moved into `Lidar/`.

## RGB source provenance — user supplied, 2026-11-13

Downloaded archive: `RGB/q3128_se_NAIP2024_RGB.zip`.

Source: <https://raster.utah.gov/>

Selection path reported by the user:

**Aerial Photography → square centered around MDRS → NAIP 2024 (60cm) → RGB**.

Extracted files:

- `RGB/q3128_se_NAIP2024_RGB.tif`
- `RGB/q3128_se_NAIP2024_RGB.tfw`

Local inspection using installed `/usr/bin/gdalinfo` found:

- CRS: NAD83 / UTM zone 12N (`EPSG:26912`).
- Pixel size: 0.6 m east–west and 0.6 m north–south (negative raster Y step).
- Dimensions: 9,122 × 11,580 pixels.
- Upper-left pixel corner: easting 516363.7468, northing 4254387.9303 m.
- Extent: easting 516363.7468–521836.9468 m;
  northing 4247439.9303–4254387.9303 m.
- Three 8-bit RGB bands; internal YCbCr JPEG compression.

The selection path is a provenance statement from the user, not an independently
repeated portal download. The CRS and raster properties above were read from the
downloaded TIFF. Acquisition year 2024 is identified by the reported portal
selection and filename.

## LiDAR source status

### Additional bare-earth DEM downloads — user supplied, 2026-11-13

Source: <https://raster.utah.gov/>

Selection path reported by the user:

**Lidar DEMs → square around East-side lowland → .5 Meter (2018) → Bare Earth DEM**.

Eight archives are present in `Lidar/`:

- `Lidar/12SWH1848.zip`
- `Lidar/12SWH1850.zip`
- `Lidar/12SWH1852.zip`
- `Lidar/12SWH1952.zip`
- `Lidar/12SWH2048.zip`
- `Lidar/12SWH2050.zip`
- `Lidar/12SWH2052.zip`
- `Lidar/12SWH2152.zip`

These are additional elevation inputs for pipeline testing. The 0.5 m resolution,
2018 date, and bare-earth designation are recorded from the user's portal
selection. All eight archives have now been extracted, and their raster metadata
and mutual grid alignment checked as documented below. Alignment with RGB
and the runtime navigation frame remains unverified. These DEM downloads are not
established as the source of the existing `input.laz` or deployed terrain maps.

### Existing point-cloud input

The existing `~/lidar` pipeline reads `input.laz`; its original download source
is not documented in the locally inspected repository history. NAIP is used
there for optional color texture, not elevation. LiDAR acquisition provenance
remains to be recovered.

See `../lidar-mr2-relationship.md` for existing terrain-product evidence and
`../operator-rgb-map.md` for dashboard tile-serving clues. The surviving tile
artifact on base has not yet been downloaded to this workspace.

## Directory history

Renamed from `rgb-tile-pipeline-testing` to `map-pipeline-testing` on 2026-11-13
at the user's request to include both RGB and LiDAR pipeline validation.

Source materials organized into `Lidar/` and `RGB/` at the user's request.

## DEM mosaic — completed 2026-11-13

All eight TIFFs have the same horizontal CRS, **NAD83(2011) / UTM zone 12N
(EPSG:6341)**, north-up 0.5 × 0.5 m pixels, one Float32 elevation band in metres,
and NoData value **-9999**. They share exact pixel-grid alignment. Their tile
footprints partition a 4,000 × 5,000 m rectangle without overlap or missing tiles.
The northern row uses four 1 km squares; the other four tiles are 2 km squares.

### Individual coverage

Coordinates below are outer raster edges in EPSG:6341, in metres.

| TIFF | Pixels (width × height) | West E | East E | South N | North N |
| --- | --- | --- | --- | --- | --- |
| 12SWH1848.tif | 4000 × 4000 | 518000 | 520000 | 4248000 | 4250000 |
| 12SWH1850.tif | 4000 × 4000 | 518000 | 520000 | 4250000 | 4252000 |
| 12SWH1852.tif | 2000 × 2000 | 518000 | 519000 | 4252000 | 4253000 |
| 12SWH1952.tif | 2000 × 2000 | 519000 | 520000 | 4252000 | 4253000 |
| 12SWH2048.tif | 4000 × 4000 | 520000 | 522000 | 4248000 | 4250000 |
| 12SWH2050.tif | 4000 × 4000 | 520000 | 522000 | 4250000 | 4252000 |
| 12SWH2052.tif | 2000 × 2000 | 520000 | 521000 | 4252000 | 4253000 |
| 12SWH2152.tif | 2000 × 2000 | 521000 | 522000 | 4252000 | 4253000 |

### Procedure and reproduction

1. Extract each ZIP's TIFF and world file into `Lidar/`, retaining the archives.
2. Inspect each TIFF with `gdalinfo`; verify matching CRS, pixel size, orientation,
   Float32 type, and NoData value. Check integer pixel offsets and that each
   output pixel is covered by exactly one source footprint.
3. Build a VRT from the eight explicitly listed source TIFFs at their native
   resolution and combined extent. Do not include the output TIFF as an input.
4. Materialize the VRT as a standalone tiled GeoTIFF with lossless DEFLATE
   compression and floating-point predictor. Preserve the native CRS and samples;
   no reprojection, interpolation, normalization, or hole filling is performed.
5. Read all source pixels in strips and compare them against their corresponding
   mosaic windows. Verify output dimensions, geotransform, and CRS.

Run from `map-pipeline-testing/` using the installed system Python GDAL bindings:

```bash
/usr/bin/python3 mosaic_dem.py
```

The script uses GDAL 3.4.1, NumPy, and Python's standard ZIP support. It recreates
the derived VRT, mosaic TIFF, and verification JSON. The equivalent mosaic
commands, run inside `Lidar/` after extraction, are:

```bash
gdalbuildvrt -resolution user -tr 0.5 0.5 -te 518000 4248000 522000 4253000 -srcnodata -9999 -vrtnodata -9999 bare_earth_2018_0p5m.vrt 12SWH1848.tif 12SWH1850.tif 12SWH1852.tif 12SWH1952.tif 12SWH2048.tif 12SWH2050.tif 12SWH2052.tif 12SWH2152.tif
gdal_translate -of GTiff -co TILED=YES -co COMPRESS=DEFLATE -co PREDICTOR=3 -co BIGTIFF=IF_SAFER bare_earth_2018_0p5m.vrt bare_earth_2018_0p5m.tif
```

### Mosaic corners

Output: `Lidar/bare_earth_2018_0p5m.tif`, **8,000 × 10,000 pixels**, 0.5 m/pixel.
Upper-left outer corner is (518000, 4253000); raster Y step is -0.5 m.
The first pixel center is (518000.25, 4252999.75).

These coordinates describe the **outer pixel edges**, not pixel centers.
Geographic coordinates use **NAD83(2011), EPSG:6318**, obtained by inverse UTM
projection; they are not asserted to be precise WGS84 coordinates.

| Corner | Easting (m) | Northing (m) | Longitude (°) | Latitude (°) |
| --- | --- | --- | --- | --- |
| NW | 518000 | 4253000 | -110.79378649 | 38.42507665 |
| NE | 522000 | 4253000 | -110.74796163 | 38.42498706 |
| SE | 522000 | 4248000 | -110.74811806 | 38.37992609 |
| SW | 518000 | 4248000 | -110.79391447 | 38.38001554 |

### Verification and alignment notes

Every source sample matches the mosaic exactly. Although the footprints form a
rectangle, the northern four source rasters contain NoData: **6,980,255 pixels**,
**8.7253%** of the 80,000,000 output pixels. These remain -9999; the mosaic is not
continuous valid terrain over its entire bounding rectangle. NoData must remain
unknown during later occupancy conversion, rather than being treated as a real
elevation or free space. No missing elevations were synthesized.

[Verification record](Lidar/mosaic-verification.json) includes source extents,
commands, corners, and per-tile equality and NoData checks.

The DEM horizontal CRS is EPSG:6341 (NAD83(2011)); RGB is EPSG:26912 (NAD83).
Both are UTM zone 12N, but their datum definitions differ. A later alignment
step must handle that distinction and the navigation frame explicitly. The
inspected TIFF metadata gives elevation units as metres but does not establish
the vertical datum; no vertical datum conversion was applied. This step produces
a DEM mosaic, not an occupancy map or proof of RGB/navigation-frame alignment.

## Comparison with existing lidar logs — 2026-11-13

This initial comparison preceded the new implementation. Its unexecuted-step
status below is historical; the subsequent runs and current status are documented
in [Lidar-pipeline/README.md](Lidar-pipeline/README.md).

Inspected `~/lidar/0p2/conversion_2026_02_01.log`, historical `conversion.log`
at commit `a3eed93`, historical `original`/`projected` gdalinfo transcripts at
`aec33fd`, current scripts, and the surviving `raw_mean.tif`, `fill_mean.tif`,
and `projfill_mean.tif` metadata.

The old source raster is 3014 × 3028 pixels in EPSG:3857 plus NAVD88 height,
with 1 m projected pixel spacing. Its historical AEQD projection has approximately
0.783 m pixels: Web Mercator pixel spacing is not local ground spacing here.
The new DEM is already a 0.5 m UTM elevation raster, so it replaces the old
point-cloud rasterization stage. Its larger east-side coverage is different;
identical raster dimensions or crop extents are not expected.

Old 0.4 m run: 1 km crop → 2500 × 2500 pixels; elevations 1363.788–1417.666 m.
Old 0.2 m run: 1.5 km crop → 7500 × 7500 pixels; elevations 1361.793–1430.402 m.
Those min/max values describe different crops, not the new mosaic's expected range.

Three rough spot comparisons using the same longitude/latitude locations and
nearest pixels show similar elevations:

| Longitude | Latitude | Old filled DEM (m) | New mosaic (m) |
| --- | --- | --- | --- |
| -110.791394 | 38.406739 | 1372.74316 | 1372.73999 |
| -110.785000 | 38.400000 | 1367.31970 | 1367.22998 |
| -110.780000 | 38.410000 | 1369.77368 | 1369.76001 |

These use OSR horizontal coordinate transformations from EPSG:4326 to each
raster's horizontal CRS, with no vertical transformation. They support broad
terrain consistency, not common acquisition provenance or a measured accuracy
claim. Sampling, datum, and source-resolution differences remain.

The reusable sequence is **DEM → appropriate local-frame reprojection → explicit
crop → resolution-scaled Horn slope → navigation image and georeferencing**.
Important adjustments before running it:

- Skip PDAL rasterization: these inputs are already bare-earth DEMs.
- The old logs used AEQD; current `make_gradient_map.sh` instead requests WGS84
  followed by a topocentric projection. That current transformation has not been
  executed or validated here. Logged success does not validate the newer script.
- The script crops around the input raster center, not its configured datum.
  The new east-side mosaic has a different center; use an explicit intended area.
- Current script datum is 38.406739, -110.791394; deployed 4 km metadata instead
  uses 38.4025461391511, -110.793850513327, NAD83(2011), and 0.5 m pixels. Choose
  the actual navigation-frame definition before generating map coordinates.
- `fill.py` interpolates NoData and hardcodes raw/fill filenames. Do not apply it
  blindly to the large northern coverage gaps. Current `filter.py` converts
  missing heights/slopes into image values without preserving a separate validity
  mask; unknown-space handling needs to be explicit before occupancy conversion.
- Current `filter.py` produces images but no longer prints the YAML/Gazebo
  mapping block seen in old logs. Retain output resolution, origin, projection,
  validity mask, and Nav2 encoding settings explicitly alongside the images.

This comparison did not execute reprojection, cropping, slope generation, or
occupancy conversion on the new mosaic, and did not modify `~/lidar`.
