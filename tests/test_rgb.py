import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen

import numpy as np
from osgeo import gdal,osr

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'RGB-pipeline'))
from generate import build,sha
from build_viewer import build_viewer
from serve import create_server


class RgbChecks(unittest.TestCase):
    def test_adjacent_rgb_sources_fill_east(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);s=osr.SpatialReference();s.ImportFromEPSG(26912)
            for name,x,width,bands,value in [('west',519000,32,3,40),('east',519019.2,32,3,160),('dem',519000,64,1,1)]:
                d=gdal.GetDriverByName('GTiff').Create(str(root/(name+'.tif')),width,32,bands,gdal.GDT_Byte)
                d.SetProjection(s.ExportToWkt());d.SetGeoTransform((x,.6,0,4251000,0,-.6))
                for i in range(1,bands+1):d.GetRasterBand(i).WriteArray(np.full((32,width),value,dtype=np.uint8))
                d=None
            c={'input':['west.tif','east.tif'],'crop_dem':'dem.tif','minzoom':18,'maxzoom':18,'display_maxzoom':22,'processes':1}
            (root/'c.json').write_text(json.dumps(c));out=root/'out';build(root/'c.json',out)
            d=gdal.Open(str(out/'work/cropped-3857.tif'));pixels=d.ReadAsArray()
            valid=pixels[3]>0
            self.assertTrue(np.any(pixels[0][valid]==40));self.assertTrue(np.any(pixels[0][valid]==160))

    def test_generation_without_node_or_viewer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            s=osr.SpatialReference();s.ImportFromEPSG(26912)
            for name,bands in [('rgb',3),('dem',1)]:
                ds=gdal.GetDriverByName('GTiff').Create(str(root/(name+'.tif')),64,64,bands,gdal.GDT_Byte)
                ds.SetProjection(s.ExportToWkt());ds.SetGeoTransform((519000,.6,0,4251000,0,-.6))
                for i in range(1,bands+1):ds.GetRasterBand(i).WriteArray(np.full((64,64),40*i,dtype=np.uint8))
                ds=None
            c={'input':'rgb.tif','crop_dem':'dem.tif','minzoom':14,'maxzoom':18,'display_maxzoom':22,'processes':1}
            (root/'config.json').write_text(json.dumps(c));out=root/'result'
            build(root/'config.json',out)
            self.assertFalse((out/'site/vendor').exists())
            self.assertFalse((out/'site/index.html').exists())
            m=json.loads((out/'manifest.json').read_text())
            self.assertTrue(all(m['tiles_per_zoom'].values()))
            for name,h in m['outputs'].items():self.assertEqual(sha(out/name),h)
            # Serving the artifact does not require a viewer or MapLibre.
            with create_server(out/'site',port=0) as server:
                t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
                try:
                    with urlopen(f'http://127.0.0.1:{server.server_port}/tiles/naip/tilejson.json') as response:
                        self.assertEqual(json.load(response)['maxzoom'],18)
                finally:server.shutdown();t.join()
            # Viewer preparation fails before touching the generated artifact.
            with self.assertRaises(ValueError):build_viewer(out,root/'absent')
            self.assertFalse((out/'site/index.html').exists())
            assets=root/'fake-assets';(assets/'dist').mkdir(parents=True)
            (assets/'package.json').write_text('{"version":"test-fixture"}')
            for f in ['dist/maplibre-gl.js','dist/maplibre-gl.css','LICENSE.txt']:(assets/f).write_text('test fixture')
            build_viewer(out,assets)
            self.assertTrue((out/'site/index.html').exists())
            self.assertEqual(json.loads((out/'manifest.json').read_text())['optional_viewer']['maplibre_version'],'test-fixture')
            with self.assertRaises(ValueError):build(root/'config.json',out)


if __name__=='__main__':unittest.main(verbosity=2)
