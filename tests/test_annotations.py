import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from osgeo import osr

spec=importlib.util.spec_from_file_location('annotations',Path(__file__).parents[1]/'Lidar-pipeline/annotate_slope.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class AnnotationChecks(unittest.TestCase):
    def test_rule_polygon_projects_all_corners_and_closes(self):
        s=osr.SpatialReference();s.ImportFromEPSG(4326)
        m={'projected_crs_wkt':s.ExportToWkt(),'geotransform':[-1,.01,0,1,0,-.01],'size':[400,400]}
        region=module.rule_outline(m,(-.5,-.5,.5,.5))
        points=region['pixel_outer_edge_coordinates']
        self.assertEqual(len(points),401)
        for index,expected in [(0,(50,50)),(100,(150,50)),(200,(150,150)),(300,(50,150)),(400,(50,50))]:
            for value,target in zip(points[index],expected):self.assertAlmostEqual(value,target,places=6)
        self.assertTrue(region['fully_inside_image'])
        with self.assertRaises(ValueError):module.rule_outline(m,(1,0,-1,1))

    def test_marker_compass_copy_and_resize(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=osr.SpatialReference();source.ImportFromEPSG(4326)
            target=osr.SpatialReference();target.ImportFromEPSG(6341)
            for s in [source,target]:s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            x,y,_=osr.CoordinateTransformation(source,target).TransformPoint(-110.7900,38.4053)
            meta={'size':[400,400],'projected_crs_wkt':target.ExportToWkt(),
                  'geotransform':[x-200,1,0,y+200,0,-1]}
            (root/'metadata.json').write_text(json.dumps(meta))
            image=root/'slope.png';Image.new('LA',(400,400),(100,255)).save(image)
            checksum=module.sha(image)
            result=module.annotate(root)
            self.assertEqual(module.sha(image),checksum)
            self.assertEqual(result['output_size'],[400,400])
            self.assertEqual(result['rule_region']['bounds_wgs84'],list(module.RULE_BOUNDS))
            self.assertAlmostEqual(result['marker_output_pixel'][0],199.5,places=6)
            self.assertAlmostEqual(result['marker_output_pixel'][1],199.5,places=6)
            vectors=result['marker']['direction_unit_vectors']
            self.assertLess(vectors['N'][1],-.99);self.assertGreater(vectors['E'][0],.99)
            self.assertGreater(vectors['S'][1],.99);self.assertLess(vectors['W'][0],-.99)
            with self.assertRaises(ValueError):module.annotate(root)
            with self.assertRaises(ValueError):module.annotate(root,image)
            with self.assertRaises(ValueError):module.annotate(root,root/'outside.png',latitude=0,longitude=0)
            small=module.annotate(root,root/'small.png',max_size=256)
            self.assertEqual(small['output_size'],[256,256])
            self.assertAlmostEqual(small['marker_output_pixel'][0],127.5,places=6)
            self.assertEqual(module.sha(image),checksum)
            no_region=module.annotate(root,root/'no-region.png',include_rule=False)
            self.assertIsNone(no_region['rule_region'])

if __name__=='__main__':unittest.main()
