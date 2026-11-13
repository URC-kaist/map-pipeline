# Offline RGB tile pipeline — research and proposed setup

Audit date: 2026-11-13. **Research complete; conversion and server implementation
have not started.** The LiDAR workflow remains settled for now. This directory
records the proposed RGB workflow for the future cartographer repository.

## Likely original tool

**GDAL's `gdal2tiles.py` is a strong match**, rather than a proven historical
identification. It generates a pyramid of small raster files and optional
Leaflet/OpenLayers HTML viewers, ready for an ordinary static HTTP server.
That matches the remembered directory tree, long conversion, and HTML page.
The old tile artifact on base may identify the tool and zooms more definitively:
look for `leaflet.html`, `openlayers.html`, `googlemaps.html`, `tilemapresource.xml`
and numeric zoom directories. Absence of tilemapresource.xml is not decisive:
the installed version does not generate it for XYZ mode.

Primary references:

- [GDAL2Tiles documentation](https://gdal.org/en/stable/programs/gdal2tiles.html).
- [Version 3.4.1 source](https://github.com/OSGeo/gdal/blob/v3.4.1/gdal/swig/python/gdal-utils/osgeo_utils/gdal2tiles.py).
- [MapLibre raster source specification](https://maplibre.org/maplibre-style-spec/sources/).
- [Python static server](https://docs.python.org/3.10/library/http.server.html).

## Dependencies: already present

The following commands were found and their help/version inspected:

- `/usr/bin/gdal2tiles.py`, also callable as
  `/usr/bin/python3 -m osgeo_utils.gdal2tiles`.
- GDAL 3.4.1: `gdalwarp`, `gdal_translate`, `gdalinfo`, Python bindings.
- Python 3.10, NumPy and Pillow.
- MapLibre GL JS **4.7.1**, its CSS and license already exist in
  `~/mr2-stack/dashboard/node_modules/maplibre-gl/`.
- Python's built-in HTTP server requires no pip package.

**No additional installation is needed for the proposed baseline on this
machine.** On a fresh Ubuntu system, the equivalent packages are `gdal-bin`,
`python3-gdal`, `python3-numpy` and `python3-pil`. Prefer matched distribution GDAL
bindings and tools over a second pip installation. MapLibre browser assets must
be vendored with their license for the standalone offline viewer; reuse the
existing installed version here and record asset hashes.

The proposed commands below target the observed GDAL **3.4.1** flags. New online
GDAL documentation also describes features absent here (such as output-driver
selection) and a future CLI migration; do not copy those flags into this version.
[Installed help](evidence/installed-gdal2tiles-help.txt) is the local reference.

## Dashboard contract

Inspected `~/mr2-stack/dashboard/src/hooks/useMapPreviewMap.ts`:

| Setting | Current value |
| --- | --- |
| Utah tile URL | `/tiles/naip/{z}/{x}/{y}.png` |
| Tile dimensions | 256 × 256 pixels |
| Generated levels implied by current source config | minzoom 14, maxzoom 22 |
| Tile indexing | MapLibre default **XYZ** (north-origin Y) |
| Projection | Global Web Mercator raster tiles, EPSG:3857 |
| Utah bounds | Currently absent; add actual source bounds later |
| Other local collections | `/tiles/kaist/…` and `/tiles/pump_track/…` |

`scripts/nginx/mr2-dashboard-locations.conf` already serves `/tiles/` from
`/var/www/mr2-tiles/`; deployment creates that directory but does not populate it.
The current `dashboard/vite.config.js` has no `/tiles` development proxy.
Historical nginx used localhost port **8088**, consistent with a separate local
static server. No changes to dashboard or nginx were made in this audit.

**Use `--xyz` explicitly.** GDAL2Tiles defaults to TMS, which reverses the Y
index relative to this dashboard. Matching filenames alone does not ensure that
imagery appears at the correct latitude.

## Zoom and size recommendation

The input is `../RGB/q3128_se_NAIP2024_RGB.tif`: 0.6 m UTM pixels,
9122 × 11580, EPSG:26912, three Byte RGB bands. It covers about 5.47 × 6.95 km.

At the image's center latitude, approximate Web Mercator ground sampling is:

| Highest physical zoom | Ground m/pixel | Total files, full image, z14 onward | DEM-sized crop envelope |
| --- | --- | --- | --- |
| 18 | 0.468 | 3,815 | 1,940 |
| 19 | 0.234 | 14,671 | 7,400 |
| 20 | 0.117 | 57,727 | 29,072 |
| 22 | 0.029 | 915,039 | 461,840 |

These are **bounding-envelope tile counts**, calculated from a virtual Mercator
warp and tile-grid intersections. Transparent-edge exclusion and the exact
crop polygon can reduce them. They are not measured output counts, disk usage
or timings. [Calculation results](evidence/tile-estimates.json).

**Recommended first run: physical tiles z14–18**, then allow the browser to
overzoom to z22. At z18 the imagery is already modestly upsampled. Higher physical
zooms cannot create finer detail from this source. MapLibre supports displaying
maxzoom tiles above that level, but its raster source `maxzoom` must be changed
to **18**; leaving it at 22 would request nonexistent higher-level tiles.
This is a proposed later dashboard change, not an edit already applied.

If exact compatibility with the current unmodified source config is required,
generate z14–22 instead. Keep this as an explicit larger-output profile rather
than the default. The remembered 2 GB does not establish which old zooms or
extent were used. For illustration only, averaging 50 KiB/tile would put the
full-image z14–20 set near 2.75 GiB and z14–22 near 43.6 GiB, before filesystem
overhead. Actual PNG compression must be measured with a pilot conversion.

## Optional LiDAR-footprint crop — user strategy

Preserve the downloaded TIFF. Create a derived crop using the stitched DEM's
**outer rectangle**, E=518000–522000 and N=4248000–4253000 in **EPSG:6341**.
Do not reuse those numbers as EPSG:26912 coordinates or assign a different CRS
without transforming them.

For implementation, write a densified boundary polygon with explicit EPSG:6341
CRS (for example, a GeoPackage cutline), then use GDAL warp/crop with that
cutline and an EPSG:3857 output. Record the polygon, transformations, output
grid and alpha mask in the manifest. A georeferenced cutline avoids confusing
source-CRS bounds, target-CRS bounds and longitude/latitude. The current GDAL
supports a cutline dataset; newer flags such as `-cutline_srs` must not be
assumed available.

The RGB's eastern edge stops roughly 160 m short of the DEM's eastern edge;
therefore the whole DEM rectangle is not covered by this RGB image. Missing
imagery must remain transparent, not extrapolated. Use the rectangle even where
the DEM itself has NoData: image coverage and valid elevation coverage are
separate concepts. The crop approximately halves tile counts, while zoom choice
still has the larger impact. Its footprint is a tilted polygon in Mercator;
the table uses the common bounding envelope, not a pixel-perfect cutline count.

RGB remains in Web Mercator tiles; terrain products can retain their UTM grid.
Alignment means agreement at transformed geographic control points, not
identical raster dimensions or projections. NAD83 versus NAD83(2011) and any
available datum transformation grids must be recorded; field registration is
still pending.

## Proposed conversion procedure

These are **future commands**, not a record of an executed conversion. Run from
`RGB-pipeline/`; the implementation will add input hashes, version checks,
configuration, progress logs, output validation and fresh output directories.

1. Inspect the source's CRS, Byte RGB bands and footprint. Do not label every
   black pixel as NoData: genuine dark imagery could be lost.
2. Prepare a Web Mercator RGBA warped VRT. The full-image example is:

   ```bash
   mkdir -p output/work output/site/tiles
   gdalwarp -of VRT -t_srs EPSG:3857 -r bilinear -dstalpha ../RGB/q3128_se_NAIP2024_RGB.tif output/work/naip-3857.vrt
   ```

   The optional crop adds the documented cutline/crop stage here. The VRT is a
   working dependency on the original TIFF, not a portable standalone image.
   Completed PNG tiles are independent of both files.

3. Generate a PNG XYZ pyramid:

   ```bash
   GDAL_CACHEMAX=128 /usr/bin/python3 -m osgeo_utils.gdal2tiles --xyz -p mercator --tilesize=256 -z 14-18 -r average --processes=4 -x -w none -n output/work/naip-3857.vrt output/site/tiles/naip
   ```

   Four workers are an initial setting, not a benchmark result. `GDAL_CACHEMAX`
   is per process. Skip fully transparent tiles, preserve edge alpha, and use
   average resampling for the pyramid. Resume (`-e`) is suitable only when input
   hash and all generation settings match a recorded unfinished run; it is not
   validation of existing files.
4. Create `tilejson.json`, bounds/zoom metadata, manifest, and offline `index.html`.
   Bundle the existing MapLibre JS/CSS and license in `site/vendor/`, use inline
   style data and only the local raster layer. Fit to actual bounds; use
   maxzoom 18 for the source and allow map zoom to 22.

The stock `-w leaflet` option would reproduce the remembered kind of HTML page,
but inspected GDAL 3.4.1 templates request JS/CSS from unpkg and include external
OSM/Carto/Stamen basemaps. Their existence is **not proof of offline operation**.
Use `-w none` plus a controlled local viewer for the final pipeline. No external
style URL, font service, image tiles, geocoder or CDN should be needed by that
viewer. This addresses map viewing; it is not an audit of every dashboard panel.

## Proposed server and deployment

```text
RGB-pipeline/
  README.md
  evidence/
  # To implement next:
  config/naip.json
  generate.py
  serve.py
  verify.py
  output/
    work/
    site/
      index.html
      vendor/                 # MapLibre JS/CSS and license
      tiles/naip/
        tilejson.json
        14/<x>/<y>.png
        …
        18/<x>/<y>.png
```

Implement `serve.py` around Python `ThreadingHTTPServer`, with explicit
`--root`, `--bind` and `--port`; default to localhost:8088 and the `site/`
directory. It serves `/`, vendor assets, metadata and `/tiles/naip/…` from one
origin. A manual equivalent for the proposed structure is:

```bash
/usr/bin/python3 -m http.server 8088 --bind 127.0.0.1 --directory output/site
```

An HTML page does not serve files itself; the HTTP server handles tile requests.
Serving the TIFF directory or opening HTML with `file://` is not the intended
workflow. For a dashboard on a different port, `/tiles/…` still targets the
dashboard's own origin. Add a Vite `/tiles` proxy to localhost:8088 during
development, or use the existing nginx static alias. Merely starting Python on
8088 does not wire the dashboard to it. Direct cross-origin tile URLs would
instead require an explicit URL change and CORS handling.

On base, the existing nginx alias can serve the generated
`site/tiles/naip/` collection as `/var/www/mr2-tiles/naip/`; Python remains the
included standalone preview/test path. No deployment, copy or server startup
has occurred in this audit.

## Acceptance checks for the next implementation

- Small pilot: confirm RGBA edge behavior, XYZ north/south orientation, tile
  dimensions, requested filenames and geographic corner/center controls.
- Measure tile count, elapsed time, bytes and filesystem space; extrapolate
  before enabling physical zoom 22. Keep crop and zoom choices in config.
- Check multiple terrain/RGB control points after CRS transformations; preserve
  transparency where either requested image coverage or source data is absent.
- Test `/tiles/naip/z/x/y.png`, metadata and viewer through the included server,
  then through the dashboard's same-origin routing.
- Disable external networking and inspect browser requests. Verify initial
  page load, panning, zooming/overzooming and attribution with only local assets.
- Confirm that maxzoom/bounds in metadata, preview and dashboard match physical
  output. Do not treat successful conversion alone as dashboard validation.

No tile files, operational server, dashboard changes, package installation or
RGB-to-LiDAR field alignment have been completed by this research step.
