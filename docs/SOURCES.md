# Source data and redistribution

**Current expanded profile (2026-11-17):** see the root
[expanded coverage record](EXPANDED-COVERAGE.md). It supersedes the original dimensions/source counts below; those describe
the initial 2018-only validation. Current commands use the expanded inputs.

The source files are **external inputs**, not normal Git objects. `sources.json`
records twenty public HTTPS download URLs from the official Utah raster catalog,
filenames, sizes, catalog IDs, product selection and SHA-256 hashes of the exact
original archives used here. Human downloading remains a fallback if the host
or catalog changes; the same checksums must pass before extraction.

```bash
/usr/bin/python3 download_sources.py
/usr/bin/python3 prepare_sources.py
```

The downloader uses `curl --fail --location`, bounded timeouts and retries,
three simultaneous downloads, staged files and checksum verification. Existing
matching files are reused; mismatches stop without replacing original inputs.
`prepare_sources.py` verifies ZIPs again before extracting only expected TIFF and
world-file entries. It refuses conflicting existing extracted files.

## Current products (expanded 4 × 5.5 km footprint)

- NAIP 2024 60 cm RGB: **q3128_se** and adjacent **q3129_sw**.
- Southern Utah 2018 QL1 0.5 m DEM: eight original files, now under `Lidar/2018/`.
- Southern Utah 2020 QL2 1 m DEM: six northern/edge fillers under `Lidar/2020/`.
- West/East Utah 2022 QL2 1 m DEM: four remaining edge fillers under `Lidar/2022/`.

| Source | File |
| --- | --- |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH1848.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH1850.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH1852.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH1952.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH2048.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH2050.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH2052.zip` |
| LiDAR2018_50cm_SouthernUtah_DEM_Tiles | `Lidar/2018/12SWH2152.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH1852.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH1853.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH1952.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH1953.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH2052.zip` |
| LiDAR2020_100cm_SouthernUtah_DEM_Tiles | `Lidar/2020/12SWH2053.zip` |
| LiDAR2022_100cm_WestEastUtah_DEM_Tiles | `Lidar/2022/12SWH2052.zip` |
| LiDAR2022_100cm_WestEastUtah_DEM_Tiles | `Lidar/2022/12SWH2053.zip` |
| LiDAR2022_100cm_WestEastUtah_DEM_Tiles | `Lidar/2022/12SWH2152.zip` |
| LiDAR2022_100cm_WestEastUtah_DEM_Tiles | `Lidar/2022/12SWH2153.zip` |
| NAIP2024_RGB_QQuads | `RGB/q3128_se_NAIP2024_RGB.zip` |
| NAIP2024_RGB_QQuads | `RGB/q3129_sw_NAIP2024_RGB.zip` |

The original portal selections and nine-file baseline are preserved in
`docs/workspace-history.md`. The expanded selection queries the same public
catalog against EPSG:6341 bounds `[518000,4248000,522000,4253500]`, retaining
only positive-area footprint intersections and selecting bare-earth DEMs.
The index includes other years and DSMs with the same short tile names, so paths
include the year and product. Checksums fingerprint the exact downloaded ZIPs;
they are local baseline hashes, not provider-published checksums.

See [expanded coverage](EXPANDED-COVERAGE.md) for priority, resolutions,
source-ID provenance, vertical limits and complete-region validation.

## Attribution and conditions

Source: Utah Geospatial Resource Center (UGRC), State Geographic Information
Datasource (SGID); NAIP imagery also credits USDA. Downloads accessed
2026-11-13/14 and 2026-11-17. Original source ZIPs are unchanged. Derived products crop,
reproject, resample, mosaic or compute terrain slopes as recorded in their
manifests; generated products must identify those modifications.

[UGRC policy](https://gis.utah.gov/documentation/policy/license/) applies CC BY
4.0 by default unless dataset metadata states otherwise. It requires attribution,
a link to the license, indication of changes, accompanying metadata and the
unmodified disclaimer. Google/Hexagon imagery and externally referenced datasets
have separate exceptions. The public aerial and lidar catalog item records
saved here include CC BY 4.0 and the full disclaimer in `licenseInfo`.

This supports redistribution subject to those conditions and any specific
dataset override; public access alone does not prove unrestricted redistribution.
We have **not** rehosted any data or asserted that the original DEM vertical
datum is established. The direct downloads avoid a need to mirror these files
on GitHub. If a future mirror is needed, retain the original bytes and relevant
metadata/attribution/disclaimer, confirm any dataset-specific terms, and use
release assets or Git LFS rather than ordinary Git history.

Data licenses are separate from this project's code license, which the user
has explicitly left undecided. Optional MapLibre assets retain their own license.
