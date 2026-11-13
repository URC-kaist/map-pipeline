# Map Pipeline

Reproducible offline map generation for the MR2 rover: bare-earth DEMs to
terrain/Nav2 cost maps, and RGB imagery to dashboard XYZ tiles.

Repository: **[URC-kaist/map-pipeline](https://github.com/URC-kaist/map-pipeline)**.
Version: `0.1.0-dev`. The code license is intentionally [undecided](CODE-LICENSE.md).

This project supersedes [URC-kaist/lidar](https://github.com/URC-kaist/lidar).
That repository is retained as a read-only development archive for the original
LiDAR processing experiments. Use this repository for current procedures.

## Quickstart

Install the [supported environment](ENVIRONMENT.md), then run from this root:

```bash
/usr/bin/python3 download_sources.py
/usr/bin/python3 prepare_sources.py
/usr/bin/python3 mosaic_dem.py
/usr/bin/python3 Lidar-pipeline/pipeline.py --output Lidar-pipeline/output/mdrs-east
/usr/bin/python3 RGB-pipeline/generate.py
/usr/bin/python3 RGB-pipeline/serve.py
```

The source downloader uses public HTTPS URLs and verifies SHA-256. Manual
portal downloads are an alternative, subject to the same checksums. See
[source provenance and conditions](docs/SOURCES.md) and [sources.json](sources.json).
Generation is offline once the source archives have been obtained.

Choose new output directories to repeat generation; existing results are never
overwritten. The RGB server serves the generated `site/` tree on localhost:8088,
including `/tiles/naip/{z}/{x}/{y}.png`. **Node and MapLibre are not required to
generate tiles, produce metadata, or serve these files.**

## Optional visualization demo

Prepare any MapLibre GL JS package separately, then add its local assets:

```bash
/usr/bin/python3 RGB-pipeline/build_viewer.py RGB-pipeline/output/mdrs-crop --assets /path/to/maplibre-gl-package
```

This package must include `dist/maplibre-gl.js`, `dist/maplibre-gl.css`,
`package.json` and `LICENSE.txt`. For example, prepare MapLibre 4.7.1 in a
separate tools directory using `npm pack maplibre-gl@4.7.1` and extract that
package there. Alternatively, download the package tarball with curl from
`https://registry.npmjs.org/maplibre-gl/-/maplibre-gl-4.7.1.tgz`; Node/npm are
not required to serve browser assets. It is an optional acquisition step, not part of map conversion.
The demo was tested with 4.7.1; `mr2-stack/node_modules` is just one possible
local asset source and is no longer hardcoded or necessary.

With the optional viewer built, open http://127.0.0.1:8088/ for the graphical
map. Without it, tile/metadata HTTP requests still work and `/` lists files.
The demo's assets are bundled locally so no Internet is needed for viewing.

## Workflows and coordinate contracts

- [Terrain pipeline](Lidar-pipeline/README.md): explicit projection/bounds/anchor,
  Horn slopes, validity masks, raw-mode Nav2 map and optional simulation meshes.
- [RGB pipeline](RGB-pipeline/README.md): crop to the DEM outer footprint,
  EPSG:3857, north-origin XYZ, 256 px PNGs, physical zooms 14–18.
- [Environment and tests](ENVIRONMENT.md): core versus optional dependencies.
- [Release status](RELEASE-REVIEW.md): what has been verified and what remains.

The DEM uses NAD83(2011)/UTM 12N (EPSG:6341); RGB uses NAD83/UTM 12N
(EPSG:26912). They are transformed, not relabeled. Web Mercator tiles and a
Nav2 local map frame are different coordinate systems. Runtime map poses reach
geographic dashboard overlays via the robot's `/toLL` transform. Source datum
operations available here are approximate; field registration is not established.

Nav2 PNGs use raw values 0–100 and 255 unknown with a matched YAML and new metadata
schema. They are not a drop-in replacement for the old mr2-stack scale-mode
cropper. Dashboard integration requires maxzoom 18, generated bounds and correct
same-origin tile routing. Its rendering choice is tracked in
[issue #82](https://github.com/URC-kaist/mr2-stack/issues/82).

## Repository layout and data policy

```text
sources.json, download_sources.py, prepare_sources.py
mosaic_dem.py
Lidar/                  # Original DEM ZIPs/extractions/mosaic, ignored
RGB/                    # Original imagery ZIP/extraction, ignored
Lidar-pipeline/          # Processing code/configs/tests and historical evidence
RGB-pipeline/            # Processing, static server and optional demo
  build_viewer.py        # The only generation step requiring MapLibre assets
  output/               # Generated tiles/site/intermediates, ignored
Lidar-pipeline/output/   # Generated terrain products, ignored
docs/                   # Source metadata, history and release evidence
tests/                  # Small synthetic integration checks
```

No original data was deleted during cleanup. History is archived in
[workspace-history.md](docs/workspace-history.md); those notes retain their
original machine/session context and are not fresh-install instructions.
Historical evidence is separate from current manifests and test reports.

## Verification

```bash
make test
```

Small synthetic checks need no source downloads or Node installation. Optional
PDAL/legacy-code comparisons skip when their inputs/dependencies are absent.
Real-data checks, optional browser checks, native Nav2 decoding and past
implementation findings are described in the workflow READMEs. The [initial GitHub CI run](https://github.com/URC-kaist/map-pipeline/actions/runs/43455153377)
passed after publication. Source-data terms and third-party licenses remain
separate from the undecided code license.
