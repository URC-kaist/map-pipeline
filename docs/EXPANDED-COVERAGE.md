# Expanded operating-area pipeline — 2026-11-17

The current default extends the original map north by **500 m**, as requested:
**4 × 5.5 km**, EPSG:6341 bounds **[518000, 4248000, 522000, 4253500]**.
The shared region and operating AOI are recorded in `map-region.json`.
It includes the rectangle whose opposite corners are **38.411, -110.786** and
**38.425, -110.768**, with about 500 m of northward margin at the latter corner.
This supersedes the original 2018-only 4 × 5 km profile and its NoData statistics.

## Inputs and deterministic priorities

Twenty checksum-pinned ZIPs in `sources.json` supply:

- **2018 Southern Utah QL1, 0.5 m DEM:** 1848, 1850, 1852, 1952, 2048, 2050,
  2052, 2152 (each has prefix `12SWH`).
- **2020 Southern Utah QL2, 1 m DEM:** 1852, 1853, 1952, 1953, 2052, 2053.
- **2022 West/East Utah QL2, 1 m DEM:** 2052, 2053, 2152, 2153.
- **NAIP 2024 RGB, 0.6 m:** `q3128_se` and adjacent `q3129_sw`.

Archives and extracted files use `Lidar/2018/`, `Lidar/2020/`, `Lidar/2022/`;
identical short filenames cannot overwrite one another. RGB files stay in `RGB/`.
The additional 2022 sources contribute to the wider margin/eastern map edges;
they were unnecessary for the smaller operating rectangle considered alone.

`mosaic_dem.py` builds the specified grid from the manifest's DEM entries in
2018→2020→2022 order. **Valid earlier samples are never replaced.** A later
source only supplies cells still unknown. Providers' different NoData values
are respected and normalized to -9999. The 1 m inputs use bilinear elevation
resampling and a separate nearest-sampled validity mask; interpolation does not
turn absent coverage into valid terrain. The 0.5 m originals keep their samples.
No hole-filling or guessed elevations are used.

`Lidar/source-id.tif` records the contributing source ID for each cell; its IDs
map to `Lidar/mosaic-verification.json`. The report records native resolutions,
source hashes, used cell counts, source CRS and overlap height differences.
An archived copy of the original eight-tile script is in `docs/legacy-mosaic-2018.py`;
it is history, not the current command.

## Reproduction

From the repository root, with new output directories:

```bash
/usr/bin/python3 download_sources.py
/usr/bin/python3 prepare_sources.py
/usr/bin/python3 mosaic_dem.py
/usr/bin/python3 Lidar-pipeline/pipeline.py --output Lidar-pipeline/output/mdrs-expanded
/usr/bin/python3 RGB-pipeline/generate.py --output RGB-pipeline/output/mdrs-expanded
/usr/bin/python3 verify_coverage.py
```

`mosaic_dem.py` refuses to replace an existing expanded mosaic. Preserve/relocate
an earlier generated result before intentionally rebuilding. Original source
archives are retained. The new source mosaic is
`Lidar/bare_earth_expanded_0p5m.tif`; the terrain configuration uses the same
bounds and 0.5 m grid. Other dataset-specific example profiles are historical
comparisons, not replacements for the expanded default.

The RGB generator now accepts either one source TIFF or a list. It mosaics the
two georeferenced NAIP inputs, transforms/crops to the DEM footprint, and renders
XYZ PNGs at physical zooms 14–18. No Node/MapLibre dependency was added to tile
generation or serving. For the optional demo:

```bash
/usr/bin/python3 RGB-pipeline/build_viewer.py RGB-pipeline/output/mdrs-expanded --assets /path/to/maplibre-gl-package
/usr/bin/python3 RGB-pipeline/serve.py
```

The server's default now points to the expanded `site/`. Its optional viewer
shows the new footprint and no longer describes a missing eastern strip.

## Completed verification

- DEM: **8,000 × 11,000 cells**, 0.5 m output spacing, **zero NoData cells**
  across the full 22 km² rectangle. Resampled 1 m sources still contain 1 m
  source detail; they are not new 0.5 m measurements.
- Terrain output: same dimensions; **37,996 unknown cost cells**, solely the
  outermost border where a full Horn neighborhood is unavailable.
- Requested operating AOI: **zero missing DEM, slope/cost-validity or RGB cells**,
  including both supplied corners. Checks cover every cell center inside the
  geographic AOI, not merely its bounding corners.
- RGB: **2,170 PNG tiles**, **169,492,988 bytes (~161.64 MiB)**; counts by zoom
  14/15/16/17/18 are **12 / 35 / 117 / 408 / 1,598**.
- The old eastern RGB gap is now opaque/covered. Tile pixel placement, dimensions,
  coordinate math, manifest hashes and HTTP routes pass.
- Browser test: all physical zooms, camera overzoom to 22 and panning pass;
  no external page requests, HTTP failures or JavaScript exceptions.
- Synthetic checks include priority-based mixed-resolution/NoData mosaicking
  and adjacent RGB inputs, in addition to the previous terrain tests.

Evidence: [AOI validity](expanded-coverage-verification.json),
[mosaic and overlaps](expanded-mosaic-verification.json),
[product sizes/corners](expanded-products.json),
[RGB checks](expanded-rgb-verification.json), and
[browser report](../RGB-pipeline/evidence/browser.json).

## Remaining interpretation limits

The terrain is mixed-year and mixed-resolution. The 2022 TIFFs explicitly label
NAVD88/Geoid18; the 2018/2020 TIFFs do not establish the vertical datum in their
inspected CRS metadata. Provider elevations are retained without a vertical
transformation. Median overlap differences are approximately -0.006…+0.045 m;
the largest source-level 95th-percentile absolute difference is about 0.107 m.
These checks support numerical consistency but do not prove vertical-datum
equivalence or guarantee a seam-free slope field. Review source provenance when
interpreting slopes near source boundaries.

Horizontal datum operations and runtime `/toLL`/`/fromLL` alignment retain the
previously documented limitations. Full data coverage does not mean obstacle-free
terrain or a demonstrated field-navigation capability. No live rover was run.
