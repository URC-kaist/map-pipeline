# Cartographer release review — 2026-11-14

Verdict: the two map-generation workflows are functional and tested locally.
The workspace is not yet a self-contained, cleaned-up cartographer release.
No repository was created, published, or retired during this review.

## Findings, in release priority order

### 1. External asset dependency prevents a standalone default RGB build

`RGB-pipeline/config/naip.json` points to
`../../../../mr2-stack/dashboard/node_modules/maplibre-gl`. A fresh cartographer
checkout has neither that repository layout nor those installed dependencies.
`generate.py` copies those assets only after doing the expensive tile conversion,
so a missing dependency fails late and discards the temporary conversion.

Before release, supply a pinned and licensed vendor-asset bundle or a documented,
repeatable asset preparation command independent of mr2-stack. Preflight all
assets and dependencies before starting conversion. Recheck the resulting site
with the browser test.

### 2. Source-data and generated-artifact packaging is unfinished

Only the pipeline output directories have Git ignore rules. The workspace root
has no data policy or ignore file; `Lidar/` currently holds about 483 MiB and
`RGB/` about 25 MiB, including original ZIPs, extracted rasters and derived
mosaic files. A blanket Git add would include large binary files unintentionally.

Before release, decide which sources belong in external downloads, Git LFS, or
release assets. Record their download selections, filenames and authoritative
checksums in a source manifest; preserve the original sources. Provide explicit
instructions to obtain and prepare them. The existing run manifests hash the
inputs actually used, but do not yet form a complete fresh-checkout data recipe.
Keep rebuildable outputs and verification baselines outside normal source commits.

### 3. Reproducible installation and release checks need one entry point

Current documentation lists installed system dependencies and records versions,
but there is no checked-in environment recipe or clean-environment verification
of the combined project. Browser and native Nav2 checks also depend on optional
machine-specific tools under `/opt/`; they should remain explicitly optional.

Before release, document one supported baseline environment, core versus optional
dependencies, asset preparation, source preparation and end-to-end commands.
Verify those instructions in an isolated checkout/environment without access to
`~/lidar` or the sibling mr2-stack. Keep small synthetic checks runnable without
the large source data; include an explicit real-data smoke-check procedure.

### 4. Reader-facing documentation and repository identity need final cleanup

The root README mixes current instructions, audit history and deferred work;
it links to audit files outside the proposed repository. Historical research
should remain distinguishable from supported commands. The workspace has no
project-level license or release/version metadata yet.

Before release, put a concise quickstart, supported inputs, coordinate/encoding
contracts and known limits first. Move historical evidence behind links, replace
out-of-repository references, choose project licensing, and verify the intended
GitHub owner/name. The user's intended name is URC-mr2/cartographer; the actual
existing lidar remote observed here is URC-kaist/lidar. No remote migration is
implied by this review.

## Settled implementation and checks

- Eight LiDAR tests pass again in this review, including analytic slopes,
  unknown-space handling, reprojection, compound-CRS elevation preservation,
  point-cloud class selection and mesh geometry.
- Prior real-data evidence verifies all 80 million DEM samples against the
  stitched input and native Nav2 raw-map decoding. Both large profiles were
  rebuilt with matching product hashes. Those large checks were not repeated
  during this review.
- RGB output contains 1,983 tiles at physical zooms 14–18, about 141 MiB, cropped
  geographically to the DEM rectangle. Per-tile and coordinate checks passed
  during implementation.
- The **current nearest-filtering viewer** passes the browser check again:
  physical tile zooms 14–18, camera overzoom to 22 and panning; 103 tile requests,
  no external page requests, HTTP errors or JavaScript exceptions. The browser
  screenshot and report were refreshed. Source imagery and generated tile files
  were not changed.
- Corrected the stale nearest-viewer verification statement and the root's
  contradictory statement that RGB generation still needed implementation.

## Explicit limits for an initial tooling release

These are documented limits, not necessarily blockers to a scoped initial
release of offline generation tools:

- Datum operations available here are approximate; vertical datum for the new
  DEM remains unestablished. No sub-metre field-registration claim is supported.
- The LiDAR local-offset frame has not been reconciled with the live rover's
  datum, heading and TF. Runtime poses should use the robot's /toLL and /fromLL
  services; a test anchor alone does not establish the runtime map transform.
- New terrain PNG/YAML use **raw costs** and a new metadata schema. The existing
  mr2-stack cropper uses scale settings and another schema. It requires an
  explicit integration change; the generated output is not a drop-in map swap.
- Dashboard integration needs source maxzoom 18, generated bounds and same-origin
  routing. Rendering choices are tracked in
  [mr2-stack issue #82](https://github.com/URC-kaist/mr2-stack/issues/82).
- The new terrain workflow intentionally preserves missing data and uses ground
  class 2 for optional point clouds. It does not reproduce every legacy behavior.

## Release completion criteria

1. Resolve standalone asset provisioning and preflight failures.
2. Finalize source-data distribution, ignore rules and checksum manifest.
3. Complete a fresh-checkout build and the documented checks in the supported
   environment.
4. Finish reader documentation, licensing and version/repository metadata.
5. Create/push the intended repository and verify the published checkout.

Retiring or replacing the old repository comes after that verification. It is
not necessary to reopen the settled LiDAR algorithms for this packaging work.
