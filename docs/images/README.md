# Compact pipeline previews

These are **visualization derivatives of real retained `mdrs-expanded` outputs**,
not invented imagery, raw output files, or dashboard integration screenshots.
The poster is 1536 × 970; each standalone panel is 368 × 630 including its legend.
Only this small, selected set belongs in Git. Source archives, full-resolution
rasters, tile pyramids and optional browser assets remain in their ignored paths.

| Asset | Interpretation |
| --- | --- |
| [Overview](pipeline-overview.jpg) | Shared elevation input plus three workflow outputs: Nav2 costmap, Gazebo terrain and RGB tiles. |
| [Elevation](elevation.png) | Provider elevations in metres, colour-mapped from the mosaicked `dem.tif`. Colour limits bracket the sampled range; no hillshade or invented relief. |
| [Nav2 costmap](nav2-costmap.png) | Actual `occupancy.png` raw values, sampled and colour-mapped over 0–100; 255 is unknown (magenta). The matched `map.yaml` is the navigation artifact. This display image is not a Nav2 input. |
| [Gazebo terrain](gazebo-terrain.jpg) / [full camera view](gazebo-camera.jpg) | Actual Gazebo Fortress camera render of the centered 400 × 550 m world, with georeferenced RGB texture. The small card crops closer to the hill and labels the rendered XYZ reference. The full camera view retains its complete field of view. No vertical exaggeration. |
| [RGB tiles](rgb-tiles.jpg) | Actual generated 256 px XYZ PNGs at physical z16, sampled onto the common projected footprint. Natural colour; original NAIP detail is 60 cm. |

The elevation, costmap and RGB maps use EPSG:6341 bounds **[518000, 4248000, 522000, 4253500] m**,
4 × 5.5 km, grid north up. The 1 km bars measure projected grid distance.
The map content is 320 × 440 samples, approximately 12.5 m apart. Nearest
sampling preserves individual sampled values but omits small features; **do not
use these previews for navigation**. Magenta indicates sampled unknown cells.
The full-resolution terrain cost has a one-cell unknown border, too thin to
appear reliably here; absence of magenta does not establish complete validity.

The current terrain configuration sets full cost at 45°:
`round(100 × clip(tan(slope) / tan(45°), 0, 1))`. The poster reads these
already-generated costs; it does not recompute slopes or invent occupancy
probabilities. This configured terrain product is not proof of traversability.

Cyan outlines mark the **400 × 550 m** Gazebo crop (1/100 of the full area).
The cyan box marks the simulation world's footprint, not the camera view boundary.
The oblique camera looks from southwest toward northeast, focusing on the hill;
the poster shows a further detail crop and has no 1 km bar. Red X = grid east,
green Y = grid north, blue Z = up; each reference arm is 20 m long, rendered in
the actual scene. XYZ letters are added to the card at projected arm endpoints.
Geometry uses 4 m sampling; the
world remains in real metres. See the [Gazebo workflow](../GAZEBO.md) for precise
crop bounds, local/world offsets and the separate collision verification.

The DEM retains provider heights without vertical conversion; source vertical
compatibility remains subject to the [expanded coverage limitations](../EXPANDED-COVERAGE.md).
RGB source EPSG:26912 was transformed to EPSG:3857 XYZ; the preview samples those
tiles in EPSG:6341 solely for comparison. Local Nav2 poses require the runtime
coordinate transform. These panels do not establish surveyed alignment or live
dashboard/robot integration. MapLibre and Node are not used for this export.

## Capture / regeneration

The retained products were generated on 2026-11-17 using the expanded profile;
the preview export was prepared on 2026-11-28. See
[expanded coverage](../EXPANDED-COVERAGE.md) for the original generation and
validation record. First run the [Gazebo export and capture commands](../GAZEBO.md)
to produce the default `mdrs-gazebo-relief` and `mdrs-gazebo-relief-capture`
directories. Then, from the repository root, run:

```bash
/usr/bin/python3 docs/prepare_previews.py --output /tmp/map-pipeline-previews
```

Choose a new output directory. The exporter refuses an existing destination,
reads original products without changing them, and verifies the terrain files
and all sampled tiles against their retained generation manifests. It needs the
core GDAL/NumPy/Pillow environment plus system DejaVu Sans fonts; no browser,
Internet, original source download or full pipeline rerun is needed if the
products and simulator capture are retained. The optional simulator is needed
only to produce a new camera capture, not to assemble the poster from an existing
one. JPEG exports are lossy; terrain PNGs use a reduced palette.

[provenance.json](provenance.json) records the source/configuration identity:
base repository revision, generation-script and input hashes, terrain/RGB
manifest hashes, exact sampled-tile hashes, output sizes/dimensions/hashes,
sampling settings, colour limits and library versions. The exporter script hash
also identifies this new capture code, which is not yet in that base revision.
It also embeds the Gazebo package/capture manifests, frame hash and exact pixel
detail crop used for the small card. The full camera
preview preserves the complete rendered field of view.
Full-resolution originals and manifests remain in
`Lidar-pipeline/output/mdrs-expanded/` and `RGB-pipeline/output/mdrs-expanded/`.

## Attribution and terms

Source: **Utah Geospatial Resource Center (UGRC), State Geographic Information
Datasource (SGID); USDA NAIP**. DEM: Southern Utah 2018 QL1 (0.5 m), Southern Utah
2020 QL2 (1 m), West/East Utah 2022 QL2 (1 m). RGB: NAIP 2024 (60 cm),
`q3128_se` and `q3129_sw`. Downloads accessed 2026-11-13/14 and 2026-11-17.
Modifications include mosaic/crop, reprojection/resampling, slope-derived costs,
colour mapping, sampled terrain meshes, textured simulator rendering,
downsampling, legends and lossy JPEG encoding for selected assets.

The selected catalog records include [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Retain the attribution, modifications, metadata and disclaimer when reusing these
previews. See [source documentation](../SOURCES.md), the exact source identities
in [sources.json](../../sources.json), and the archived
[aerial](../catalog/aerial-item.json) / [LiDAR](../catalog/lidar-item.json) catalog
terms. The project's [code license remains undecided](../../CODE-LICENSE.md);
this visual update does not select one.

The following unmodified disclaimer is retained from the catalog's `licenseInfo`:

> The data, including but not limited to geographic data, tabular data, and analytical data, are provided "as is" and "as available", with no guarantees relating to the availability, completeness, or accuracy of data, and without any express or implied warranties. These data are provided as a public service for informational purposes only. You are solely responsible for obtaining the proper evaluation of a location and associated data by a qualified professional. UGRC reserves the right to change, revise, suspend or discontinue published data and services without notice at any time. Neither UGRC nor the State of Utah are responsible for any misuse or misrepresentation of the data. UGRC and the State of Utah are not obligated to provide you with any maintenance or support. The user assumes the entire risk as to the quality and performance of the data. You agree to hold the State of Utah harmless for any claims, liability, costs, and damages relating to your use of the data. You agree that your sole remedy for any dissatisfaction or claims is to discontinue use of the data.
