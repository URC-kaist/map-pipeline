# Source data and redistribution

The source files are **external inputs**, not normal Git objects. `sources.json`
records nine public HTTPS download URLs from the official Utah raster catalog,
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

## Products

- RGB: raster.utah.gov → Aerial Photography → square centered around MDRS →
  **NAIP 2024 (60cm) → RGB**, `q3128_se_NAIP2024_RGB.zip`.
- Elevation: raster.utah.gov → Lidar DEMs → east-side lowland →
  **.5 Meter (2018) → Bare Earth DEM**, the eight `12SWH*.zip` entries in the
  manifest. Catalog records identify **Southern Utah 2018 / QL1 / DEMs**.

The index contains other years and DSMs with identical short tile names.
Use the recorded product/path, not filename matching alone. Discovery used
the public catalog's `PATH + TILE + EXT`, rather than guessing storage paths.
The original catalog items and selected query results are archived in
`docs/catalog/`. The catalog is a discovery source; the local SHA-256 values
are our baseline fingerprints, not provider-published checksums.

## Attribution and conditions

Source: Utah Geospatial Resource Center (UGRC), State Geographic Information
Datasource (SGID); NAIP imagery also credits USDA. Downloads accessed
2026-11-13/14. Original source ZIPs are unchanged. Derived products crop,
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
