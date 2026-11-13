# Release preparation status — 2026-11-14

The earlier [review](docs/release-review-2026-11-14.md) is archived. Current changes:

- RGB conversion and serving no longer require MapLibre, Node, or mr2-stack.
  The graphical viewer is a separate optional build step.
- Public source catalog URLs and checksums are in sources.json; curl acquisition
  and verified extraction are implemented. Original binaries and outputs are
  ignored by Git, while their provenance stays in source control.
- Root quickstart, environment instructions, optional dependency boundaries and
  synthetic CI checks are present. Fresh-checkout results are recorded in docs/.
- The source code license remains undecided at the user's request. Source data
  follows its own terms. Source binaries and generated products remain outside
  Git; the repository destination is URC-kaist/map-pipeline.

The private repository is published as URC-kaist/map-pipeline, superseding
URC-kaist/lidar. The latter is archived with a migration notice and homepage
pointing to its successor. The published checkout and initial GitHub CI passed. An openly
licensed public release would still require a code-license decision. Field registration
and runtime Nav2 cropper integration remain explicit limitations rather than
claims of completion. Existing LiDAR numerical algorithms were not changed.

## Completed fresh-checkout verification

[Results](docs/fresh-checkout-verification.json): the source-only Git clone passed
7 LiDAR tests (1 optional legacy comparison skipped) and the RGB integration
check. Using independently downloaded ZIPs, it rebuilt the stitched mosaic,
the full 80-million-cell terrain output, and 1,983 RGB tiles without viewer
assets. All terrain products and every RGB PNG match their earlier baseline
hashes. Tile serving and geographic checks passed without Node/MapLibre.
See [direct-download checks](docs/download-verification.json) and
[real RGB verification](docs/fresh-rgb-verification.json).

The code-license decision remains intentionally deferred. Repository publication
does not select a code license or create a versioned GitHub Release.
