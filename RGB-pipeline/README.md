# Cropped offline RGB tile pipeline

**Current expanded profile (2026-11-17):** see the root
[expanded coverage record](../docs/EXPANDED-COVERAGE.md). It supersedes the original dimensions/source counts below; those describe
the initial 2018-only validation. Current commands use the expanded inputs.

Implemented and tested 2026-11-13. The original
[research plan](research-plan.md) is retained as history; this file describes
the actual current setup. No packages were installed and `~/mr2-stack` was not
modified. Sources remain in `../RGB/` and `../Lidar/`.

## Run and preview

From `map-pipeline-testing/RGB-pipeline/`:

```bash
/usr/bin/python3 generate.py
/usr/bin/python3 serve.py
```

Generation and serving require **no Node or MapLibre**. They produce and serve
tile files independently. To add the optional graphical demo, run:

```bash
/usr/bin/python3 build_viewer.py output/mdrs-expanded --assets /path/to/maplibre-gl-package
```

The package must contain `dist/maplibre-gl.js`, `dist/maplibre-gl.css`,
`package.json`, and `LICENSE.txt`. It may come from any separately prepared
MapLibre package; no sibling mr2-stack checkout is required. Missing demo assets
fail in this separate step without discarding generated tiles. Without this
step, the server still serves `/tiles/naip/…`; `/` is a directory listing.

Open **http://127.0.0.1:8088/** after adding the viewer. The generated result already exists at
`output/mdrs-expanded/`, so only the server command is needed to view it. The server
runs until Ctrl-C. Use `--bind 0.0.0.0` explicitly if LAN access is wanted.

For a new conversion, choose a fresh output directory:

```bash
/usr/bin/python3 generate.py --config config/naip.json --output output/repeat
/usr/bin/python3 serve.py --root output/repeat/site --port 8088
```

Existing outputs are refused. Config input paths resolve relative to the config.
The core uses system GDAL 3.4.1 and its Python bindings. NumPy/Pillow are used
by verification; the server uses Python's standard library. MapLibre assets and their license are optional viewer dependencies supplied
explicitly to `build_viewer.py`. The tested demo uses version 4.7.1.
Network access is unnecessary for generation once sources are downloaded.

## Procedure and products

1. Read the RGB TIFF's actual CRS, EPSG:26912 (NAD83 / UTM zone 12N).
2. Read the stitched DEM's outer extent in its own EPSG:6341 CRS. Write a
   georeferenced, densified polygon to `work/crop.gpkg`.
3. Crop/reproject with GDAL using that polygon into an RGBA Web Mercator
   GeoTIFF, `work/cropped-3857.tif`. Bilinear interpolation is explicit; output
   resolution is the z18 Web Mercator grid spacing (about 0.597 projected
   metres/pixel, about 0.468 ground m/pixel at MDRS). Grid edges are aligned.
4. Run GDAL2Tiles with **XYZ, 256 px PNG, zooms 14–18**, average pyramid
   resampling and four workers. Retain fully transparent tiles so requests in
   the uncovered eastern strip return valid blank PNGs instead of 404s.
5. Generate bounds/zoom metadata and a manifest with settings,
   source hashes, output hashes, counts, byte size, timing and versions.

The crop follows the DEM's **outer rectangle**, not its valid-elevation mask.
Where the downloaded RGB stops short of the rectangle, imagery is transparent.
No black-color NoData rule is imposed. Native RGB and DEM datum definitions
are transformed; they are not relabeled as if their CRS were identical.

```text
RGB-pipeline/
├── config/naip.json
├── generate.py
├── build_viewer.py          # Optional demo only
├── viewer.html
├── serve.py
├── verify.py
├── browser_check.py, browser_check.mjs
├── evidence/
├── research-plan.md
└── output/mdrs-expanded/
    ├── manifest.json, generation.log, generate_source.py
    ├── work/crop.gpkg, cropped-3857.tif
    └── site/
        ├── index.html, crop-outline.geojson
        ├── vendor/                    # JS, CSS and license; all local
        └── tiles/naip/
            ├── tilejson.json
            └── 14…18/<x>/<y>.png
```

`output/` is rebuildable and ignored by Git. `site/` is portable and sufficient
for viewing; it does not need the original TIFF or intermediate files. A sparse
pilot is retained separately at `output/pilot-sparse/` for history. It omits
fully transparent tiles and is not the recommended viewer result.

## Projection verification and Nav2 distinction

The verified image path is:

```text
RGB pixels + EPSG:26912 → EPSG:3857 → north-origin XYZ → MapLibre
DEM crop polygon + EPSG:6341 ────────┘
Nav2 map pose → live /toLL → longitude/latitude → MapLibre overlay
```

The dashboard's `useMapPreviewData.ts` explicitly calls
`robot_localization/srv/ToLL` at `/toLL` for map-frame poses and reads
longitude/latitude from its response. GNSS fixes are already geographic.
Its map component supplies these coordinates to MapLibre. Thus RGB tiles must
use the standard web map grid, **not Nav2 local x/y**. Nav2's world-to-geographic
transform incorporates the running datum, heading and potentially grid
convergence; subtracting a chosen anchor alone is not a substitute for `/toLL`.
See [robot_localization's GPS integration](https://github.com/cra-ros-pkg/robot_localization/blob/rolling-devel/doc/integrating_gps.rst).

Checks at four interior control locations confirm:

- Source UTM → Mercator → source UTM roundtrip error below 1.3e-9 m.
- Mercator coordinates match an independent spherical Mercator formula after
  geographic conversion, within 1e-6 m numerical tolerance.
- Independent longitude/latitude → XYZ tile/pixel addressing agrees with the
  cropped raster's RGBA samples (at most two byte levels allowed per channel).
- A point inside the DEM rectangle but beyond the RGB's east edge has alpha 0.

These numerical tolerances describe **arithmetic consistency, not field
accuracy**. Installed PROJ reports a nominal 4 m NAD83→WGS84 operation, a nominal
2 m NAD83(2011)→WGS84 operation, and only a ballpark NAD83(2011)→NAD83 operation
for the direct crop relation. No precise datum grid or epoch correction was
established. Exact camera/rover-to-image registration still requires surveyed
control or live `/toLL` checks. The existing LiDAR pipeline's local-offset map
is also a test frame until aligned to the runtime robot transform.

Detailed operation descriptions and coordinates are in
[verification.json](evidence/verification.json). This verifies that the chosen
projection path is appropriate and implemented consistently; it does not claim
that the existing Nav2 map cropper's translation-only approximation is exact.

## Results and checks

Actual output: **1,983 tiles**, **147,485,541 bytes (140.65 MiB)** of PNGs,
generated in about **82.5 seconds** on this machine. Intermediate TIFFs, browser
assets and filesystem overhead are additional. Counts by zoom:

| Zoom | PNG count |
| --- | --- |
| 14 | 9 |
| 15 | 30 |
| 16 | 108 |
| 17 | 374 |
| 18 | 1,462 |

```bash
/usr/bin/python3 verify.py output/mdrs-expanded
/usr/bin/python3 browser_check.py output/mdrs-expanded
```

`verify.py` checks every PNG, dimensions, manifest hashes, control-point pixel
placement, projection arithmetic, transparency, metadata and localhost HTTP
routes. Binding a local socket requires execution outside this session's sandbox.

`browser_check.py` uses the installed headless Brave browser and Node 24's
built-in WebSocket, without Playwright installation. It intercepts page requests,
permits only the local server plus data/blob resources, and disables cache.
It tests initial load, panning, and display zoom 22 while checking that physical
tile requests stay within zooms 14–18. See
[browser report](evidence/browser.json) and [viewer screenshot](evidence/viewer.png).
The first browser harness attempt had a DOM-name collision and a later return
value serialization issue; both were corrected before the final run.

## Dashboard integration

The generated standalone viewer works with the existing dashboard's MapLibre
version and URL contract. To integrate these tiles into `mr2-stack`, set its
`local_naip` source to the generated bounds, `scheme: 'xyz'`, `tileSize: 256`,
`minzoom: 14`, and **`maxzoom: 18`**. Map zoom may still reach 22 through
overzooming. The existing source maxzoom 22 would request files not generated
by this profile. Bounds are recorded in `site/tiles/naip/tilejson.json`.

The Python server serves `/tiles/naip/…` from `site/`. During Vite development,
a `/tiles` proxy to localhost:8088 is needed because relative URLs otherwise
target the Vite origin. On base, existing nginx can serve this collection from
`/var/www/mr2-tiles/naip/`. The HTML page is a viewer; the HTTP server supplies
the tile files. No map service backend or Internet imagery provider is required.

The original dashboard, nginx configuration and live robot have not been
changed, launched or deployed by this pipeline test.

## Image sharpness and zoom

The source imagery has **0.6 m pixels**. Generated z18 tiles sample about
**0.468 ground m/pixel** at MDRS; this modest upsampling adds no source detail.
MapLibre uses a 512-pixel zoom convention, whereas these XYZ tiles are 256 px:
physical tile z18 corresponds approximately to camera zoom 17. At camera zoom
22, one z18 tile pixel occupies about **32 × 32 CSS screen pixels** (before
screen device-pixel ratio). A CSS screen pixel then spans about 0.0146 m on the
ground; this is magnification, not centimetre-resolution imagery.

The original viewer used MapLibre's default linear raster resampling, which
blends adjacent pixels and looks blurry when overzoomed. The viewer now sets
`raster-resampling: nearest` on the raster layer, preserving visible tile-pixel
boundaries. Its legend states the 60 cm source resolution and explains that
higher zoom enlarges existing detail. This affects browser display only;
generated tiles retain their original bilinear reprojection and average pyramid
resampling, and the source itself uses JPEG compression.

For the dashboard, use the same layer paint property:

```javascript
paint: { 'raster-resampling': 'nearest' }
```

Nearest rendering gives crisp blocks, not additional terrain detail. Limiting
camera zoom to about 17–18 is another option if heavy magnification is unwanted.
Regenerating higher zoom tiles from the same source will not restore finer
detail. Changing conversion interpolation can alter appearance but is not a
substitute for higher-resolution source imagery. The original dashboard has
not been edited.

The nearest-display viewer was rechecked during the 2026-11-14 release review.
The current browser report and screenshot now reflect nearest filtering; all
physical zooms, overzoom and panning pass with no external page requests or errors.
