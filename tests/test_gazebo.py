"""Small synthetic checks for crop placement, RGB registration and SDF packaging."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from osgeo import gdal, osr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Lidar-pipeline'))
from export_gazebo import package
from verify_gazebo import ground_at


class GazeboExportTests(unittest.TestCase):
    def test_collision_height_uses_triangle_interpolation(self):
        triangles = np.array([[[0, 0, 10], [2, 0, 14], [0, 2, 12]]], dtype=float)
        self.assertAlmostEqual(ground_at(triangles, .5, .5), 11.5)
        with self.assertRaisesRegex(ValueError, 'left the mesh'):
            ground_at(triangles, 1.5, 1.5)

    def fixture(self, root):
        terrain = root/'terrain'
        terrain.mkdir()
        crs = osr.SpatialReference()
        crs.ImportFromEPSG(6341)
        wkt = crs.ExportToWkt()
        gt = [518000, .5, 0, 4253000, 0, -.5]
        dem = gdal.GetDriverByName('GTiff').Create(str(terrain/'dem.tif'), 40, 60, 1, gdal.GDT_Float32)
        dem.SetGeoTransform(gt)
        dem.SetProjection(wkt)
        dem.GetRasterBand(1).SetNoDataValue(-9999)
        rr, cc = np.mgrid[:60, :40]
        dem.GetRasterBand(1).WriteArray(100+rr*.1+cc*.2)
        dem = None
        (terrain/'metadata.json').write_text(json.dumps({
            'size': [40, 60], 'geotransform': gt, 'projected_crs_wkt': wkt,
            'local_frame': 'projected grid minus anchor',
            'anchor': {'projected_m': [518000, 4253000]}}))
        textures = []
        # Adjacent sources, split through the center: red west, blue east.
        for i, color in enumerate([(255, 0, 0), (0, 0, 255)]):
            path = root/f'rgb-{i}.tif'
            rgb = gdal.GetDriverByName('GTiff').Create(str(path), 20, 60, 3, gdal.GDT_Byte)
            rgb.SetGeoTransform([518000+i*10, .5, 0, 4253000, 0, -.5])
            rgb.SetProjection(wkt)
            for band, value in enumerate(color, 1):
                rgb.GetRasterBand(band).Fill(value)
            rgb = None
            textures.append(path)
        return terrain, textures

    def test_center_crop_coordinates_texture_and_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            terrain, textures = self.fixture(root)
            out = root/'gazebo'
            record = package(terrain, out, textures, .25, 4)
            self.assertEqual(record['crop_pixel_window'], [10, 15, 20, 30])
            self.assertEqual(record['crop_size_m'], [10, 15])
            self.assertEqual(record['actual_area_fraction'], .25)
            self.assertEqual(record['world_to_navigation_xy_offset_m'], [10, -15])
            origin = record['world_to_projected']
            self.assertEqual(origin['scale'], 1)
            lines = (out/'model/terrain.obj').read_text().splitlines()
            vertices = np.array([[float(x) for x in s.split()[1:]]
                                 for s in lines if s.startswith('v ')])
            np.testing.assert_allclose(vertices[0, :2], [-4.75, 7.25])
            self.assertEqual(vertices[:, 2].min(), 0)
            normals = np.array([[float(x) for x in s.split()[1:]]
                                for s in lines if s.startswith('vn ')])
            np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-8)
            self.assertTrue((normals[:, 2] > 0).all())
            texture = gdal.Open(str(out/'model/texture.png')).ReadAsArray()
            np.testing.assert_array_equal(texture[:3, 10, 2], [255, 0, 0])
            np.testing.assert_array_equal(texture[:3, 10, -3], [0, 0, 255])
            for path in [out/'world.sdf', out/'model/model.sdf']:
                tree = ET.parse(path)
                for uri in tree.findall('.//mesh/uri'):
                    self.assertTrue((path.parent/uri.text).is_file())
            self.assertFalse(ET.parse(out/'world.sdf').findall('.//include'))
            world = ET.parse(out/'world.sdf')
            axes = world.find('.//model[@name="presentation_axes"]')
            self.assertEqual(len(axes.findall('.//visual')), 3)
            self.assertFalse(axes.findall('.//collision'))
            self.assertEqual(record['presentation']['axes_length_m'], 20)
            self.assertLess(record['presentation']['camera_pose'][4], .5)
            for name in record['outputs']:
                if name.endswith('.json'):
                    self.assertNotIn(str(root), (out/name).read_text())
            with self.assertRaisesRegex(ValueError, 'new output'):
                package(terrain, out, textures)

    def test_unknown_terrain_and_missing_rgb_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            terrain, textures = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'RGB sources do not fully cover'):
                package(terrain, root/'missing-rgb', textures[:1], .25, 4)
            self.assertFalse((root/'missing-rgb').exists())
            ds = gdal.Open(str(terrain/'dem.tif'), gdal.GA_Update)
            ds.GetRasterBand(1).WriteArray(np.array([[-9999]], dtype='float32'), 20, 30)
            ds = None
            with self.assertRaisesRegex(ValueError, 'unknown terrain'):
                package(terrain, root/'unknown', textures, .25, 4)
            with self.assertRaisesRegex(ValueError, 'area_fraction'):
                package(terrain, root/'bad', textures, 0, 4)


if __name__ == '__main__':
    unittest.main()
