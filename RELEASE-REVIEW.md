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
  follows its own terms. No data mirror, GitHub repository, push or release has
  been performed.

A locally verified development repository can be reviewed now. An openly licensed
public release still requires the code-license decision, destination confirmation,
a published-checkout/hosted CI check, and normal release tagging. Field registration
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

The local repository is prepared for review. There is no configured remote and
no published release; the code-license decision remains intentionally deferred.
