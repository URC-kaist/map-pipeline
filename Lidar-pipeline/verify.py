#!/usr/bin/python3
"""Analytic terrain, NoData, geometry, reproducibility and optional native Nav2 checks."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from osgeo import gdal
from PIL import Image
from scipy.ndimage import convolve

from pipeline import build, crs, horn, occupancy, digest, validate_config

ROOT = Path(__file__).resolve().parent


def fixture(folder, hole=False):
    h, w = 31, 29
    x = 518000 + (np.arange(w)+.5)*.5
    y = 4253000 - (np.arange(h)+.5)*.5
    z = (1400 + .1*(x[None, :]-518000) + .2*(y[:, None]-4253000)).astype(np.float32)
    if hole:
        z[15, 14] = -9999
    d = gdal.GetDriverByName('GTiff').Create(str(folder/'input.tif'), w, h, 1, gdal.GDT_Float32)
    d.SetGeoTransform((518000, .5, 0, 4253000, 0, -.5))
    d.SetProjection(crs('EPSG:6341').ExportToWkt())
    d.GetRasterBand(1).SetNoDataValue(-9999)
    d.GetRasterBand(1).SetUnitType('metre')
    d.GetRasterBand(1).WriteArray(z)
    d = None
    config = {
        'input': 'input.tif', 'source_vertical_datum': 'synthetic', 'target_crs': 'EPSG:6341',
        'anchor': {'crs': 'EPSG:6318', 'longitude': -110.793850513327, 'latitude': 38.4025461391511},
        'bounds': [518000, 4253000-h*.5, 518000+w*.5, 4253000],
        'resolution_m': .5, 'resampling': 'bilinear', 'full_cost_slope_deg': 45,
    }
    (folder/'config.json').write_text(json.dumps(config))
    return config, z


class TerrainChecks(unittest.TestCase):
    def test_analytic_plane_and_unknown_neighborhood(self):
        x, y = np.meshgrid(np.arange(9)*.5, -np.arange(9)*.5)
        z = 1200 + .3*x + .4*y
        dx, dy, valid = horn(z, .5)
        np.testing.assert_allclose(dx, .3, atol=1e-9)
        np.testing.assert_allclose(dy, .4, atol=1e-9)
        np.testing.assert_array_equal(occupancy(np.hypot(dx, dy), valid, 45), 50)
        z[4, 4] = np.nan
        dx, dy, valid = horn(z, .5)
        self.assertEqual(int((~valid).sum()), 9)
        self.assertTrue(np.all(occupancy(np.hypot(dx, dy), valid, 45)[~valid] == 255))

    def test_rejects_bad_geometry_and_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = fixture(Path(tmp))
            for key, value in [('resolution_m', .7), ('resolution_m', 0),
                               ('full_cost_slope_deg', 90), ('target_crs', 'EPSG:4326')]:
                bad = dict(config, **{key: value})
                with self.assertRaises(ValueError):
                    validate_config(bad)

    def test_end_to_end_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, z = fixture(folder, hole=True)
            meta = build(folder/'config.json', folder/'first')
            build(folder/'config.json', folder/'second')
            d = gdal.Open(str(folder/'first/dem.tif'))
            np.testing.assert_array_equal(d.ReadAsArray(), z)
            slope = gdal.Open(str(folder/'first/slope_degrees.tif')).ReadAsArray()
            valid = slope != -9999
            np.testing.assert_allclose(slope[valid], np.degrees(np.arctan(np.hypot(.1, .2))), atol=.01)
            # Full perimeter and the 3x3 hole neighborhood must stay unknown.
            cost = np.asarray(Image.open(folder/'first/occupancy.png'))
            self.assertTrue(np.all(cost[~valid] == 255))
            self.assertTrue(np.all(cost[0] == 255) and np.all(cost[-1] == 255))
            self.assertTrue(np.all(cost[:, 0] == 255) and np.all(cost[:, -1] == 255))
            self.assertEqual(meta['unknown_cost_pixels'], 2*29+2*29+9)
            ax, ay = meta['anchor']['projected_m']
            np.testing.assert_allclose(meta['yaml_origin_lower_left'][:2],
                                       [518000-ax, 4253000-31*.5-ay])
            for p in (folder/'first').iterdir():
                if p.name != 'manifest.json':
                    self.assertEqual(digest(p), digest(folder/'second'/p.name), p.name)
            with self.assertRaises(ValueError):
                build(folder/'config.json', folder/'first')
            manifest = json.loads((folder/'first/manifest.json').read_text())
            for name, checksum in manifest['outputs'].items():
                self.assertEqual(digest(folder/'first'/name), checksum)

    def test_explicit_reprojection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config, _ = fixture(folder)
            from osgeo import osr
            s = crs('EPSG:6341')
            lon, lat, _ = osr.CoordinateTransformation(s, crs('EPSG:6318')).TransformPoint(518007,4252992)
            config['target_crs'] = f'+proj=aeqd +lat_0={lat} +lon_0={lon} +ellps=GRS80 +units=m +type=crs'
            config['anchor'] = {'crs': 'EPSG:6318', 'longitude': lon, 'latitude': lat}
            config['bounds'] = [-4,-4,4,4]
            (folder/'config.json').write_text(json.dumps(config))
            meta = build(folder/'config.json', folder/'reprojected')
            self.assertEqual(meta['size'], [16, 16])
            np.testing.assert_allclose(meta['anchor']['projected_m'], [0,0], atol=1e-6)
            self.assertGreater(meta['valid_slope_pixels'], 0)

    def test_compound_input_preserves_elevations(self):
        from osgeo import osr
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, z = fixture(folder)
            compound = osr.SpatialReference()
            compound.SetCompoundCS('Synthetic projected CRS + NAVD88 height',
                                   crs('EPSG:6341'), crs('EPSG:5703'))
            d = gdal.Open(str(folder/'input.tif'),gdal.GA_Update)
            d.SetProjection(compound.ExportToWkt())
            d = None
            build(folder/'config.json',folder/'horizontal')
            d = gdal.Open(str(folder/'horizontal/dem.tif'))
            np.testing.assert_array_equal(d.ReadAsArray(), z)
            self.assertFalse(d.GetSpatialRef().IsCompound())

    def test_legacy_horn_magnitude(self):
        # Execute the unchanged mathematical function from the local legacy code,
        # without importing its missing rasterio dependency.
        import os
        legacy_path = os.environ.get('CARTOGRAPHER_LEGACY_FILTER')
        if not legacy_path:
            self.skipTest('Optional legacy comparison: set CARTOGRAPHER_LEGACY_FILTER')
        legacy = Path(legacy_path)
        if not legacy.exists():
            self.skipTest('Optional local legacy comparison: ~/lidar is absent')
        parsed = ast.parse(legacy.read_text())
        function = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'compute_features')
        scope = {'np': np, 'convolve': convolve}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(legacy), 'exec'), scope)
        rng = np.random.default_rng(13)
        z = rng.normal(size=(30,30)).astype(np.float32)
        old_dx, old_dy = scope['compute_features'](z, .5, .5)
        dx, dy, _ = horn(z, .5)
        np.testing.assert_allclose(np.hypot(dx,dy), np.hypot(old_dx[1:-1,1:-1],old_dy[1:-1,1:-1]),
                                   rtol=2e-5, atol=1e-6)

    def test_ground_class_pointcloud_path(self):
        import shutil
        if not shutil.which('pdal'):
            self.skipTest('Optional LAS/LAZ path requires PDAL')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config, _ = fixture(folder)
            lines = ['X,Y,Z,Classification']
            for y in range(6):
                for x in range(6):
                    lines += [f'{518000+x},{4253000+y},100,2',
                              f'{518000+x},{4253000+y},3000,1']
            (folder/'points.csv').write_text('\n'.join(lines)+'\n')
            stages = {'pipeline': [
                {'type': 'readers.text', 'filename': str(folder/'points.csv'), 'separator': ','},
                {'type': 'writers.las', 'filename': str(folder/'points.las'), 'a_srs': 'EPSG:6341'}]}
            (folder/'make-las.json').write_text(json.dumps(stages))
            subprocess.run(['pdal', 'pipeline', str(folder/'make-las.json')], check=True,
                           capture_output=True)
            config['input'] = 'points.las'
            config['pointcloud'] = {'crs': 'EPSG:6341', 'resolution_m': .5, 'ground_classes': [2]}
            config['bounds'] = [518000,4253000,518005,4253005]
            (folder/'config.json').write_text(json.dumps(config))
            meta = build(folder/'config.json', folder/'ground')
            self.assertGreater(meta['valid_elevation_pixels'], 0)
            np.testing.assert_allclose(meta['elevation_range_m'], [100, 100], atol=1e-6)

    def test_mesh_coordinates_holes_and_binary_format(self):
        from export_mesh import export
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fixture(folder, hole=True)
            meta = build(folder/'config.json', folder/'terrain')
            record = export(folder/'terrain', folder/'mesh', stride=4)
            self.assertGreater(record['triangles'], 0)
            self.assertEqual((folder/'mesh/terrain.stl').stat().st_size,
                             84+50*record['triangles'])
            lines = (folder/'mesh/terrain.obj').read_text().splitlines()
            v = np.array([[float(x) for x in line.split()[1:]] for line in lines if line.startswith('v ')])
            ax, ay = meta['anchor']['projected_m']
            np.testing.assert_allclose(v[0,:2], [518000.25-ax,4252999.75-ay], atol=1e-6)
            # Check upward winding and that no triangles cross the synthetic hole.
            local_hole = [518007.25-ax,4252992.25-ay]
            for line in lines:
                if line.startswith('f '):
                    indices = [int(i.split('/')[0])-1 for i in line.split()[1:]]
                    tri = v[indices]
                    self.assertGreater(np.cross(tri[1]-tri[0],tri[2]-tri[0])[2], 0)
                    inside = (tri[:,0].min() <= local_hole[0] <= tri[:,0].max() and
                              tri[:,1].min() <= local_hole[1] <= tri[:,1].max())
                    self.assertFalse(inside)


if __name__ == '__main__':
    unittest.main(verbosity=2)
