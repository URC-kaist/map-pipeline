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

if __name__=='__main__':unittest.main()
