# Supported baseline and checks

The implementation was verified on Ubuntu 22.04 with system Python 3.10,
GDAL 3.4.1, PROJ 8.2.1, NumPy, Pillow and SciPy. Use the matching distribution
GDAL bindings rather than an unrelated pip GDAL wheel.

Install the core build/check environment:

```bash
sudo apt-get update
sudo apt-get install -y make curl gdal-bin python3-gdal python3-numpy python3-pil python3-scipy
```

Core processing needs GDAL/NumPy; Pillow and SciPy support tests. `curl` is for
source acquisition. `pdal` is optional, for LAS/LAZ ingestion and its synthetic
test. Core tests skip that path if PDAL is absent. The comparison against the
old local code is optional: set `CARTOGRAPHER_LEGACY_FILTER` to its `filter.py`.
No test needs an existing `~/lidar` or `~/mr2-stack` by default.

```bash
make test
```

The RGB synthetic test makes real 14–18 tiles from a tiny generated GeoTIFF,
verifies that no viewer/Node dependency is accessed, tests serving metadata over
localhost and checks optional viewer failure/success independently. It downloads
no data. Its HTTP socket must be permitted by the execution environment.

`.github/workflows/test.yml` runs the same checks on Ubuntu 22.04. The initial hosted run passed after publication; see
[publication verification](docs/publication.json).

Additional checks:

- Optional [Gazebo terrain workflow](docs/GAZEBO.md): Gazebo Fortress 6.18.0,
  Physics/Sensors/SceneBroadcaster plugins and OGRE2/OpenGL for rendering.
  Mesh/world generation and synthetic checks need no simulator; actual capture
  and collision checks are separate optional commands.
- Real RGB dataset: `RGB-pipeline/verify.py` checks every PNG, source-coordinate
  controls, manifest hashes and HTTP routes; an optional demo is checked only
  when present.
- `RGB-pipeline/browser_check.py` additionally needs Node 24 and a local
  Chromium-family browser (`--browser` selects its path). These are optional
  visualization tests, not processing/server dependencies.
- `Lidar-pipeline/check_nav2.py` additionally needs ROS Humble Nav2 libraries,
  headers and g++; no ROS nodes are launched.

Fresh-checkout verification uses a separate temporary Git clone with no sibling
mr2-stack or lidar repository. The core and real-data tests use only checked-in
code and downloaded, checksum-verified archives. This is a clean filesystem
checkout test on the existing supported host, not a new operating-system image
or a guarantee of bit-identical compression across GDAL/PROJ versions.
