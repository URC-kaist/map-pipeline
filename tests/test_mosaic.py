import importlib.util
from pathlib import Path
import tempfile
import unittest
import numpy as np
from osgeo import gdal,osr

spec=importlib.util.spec_from_file_location('mosaic',Path(__file__).parents[1]/'mosaic_dem.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class MosaicChecks(unittest.TestCase):
    def test_priority_mixed_resolution_and_nodata(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[];s=osr.SpatialReference();s.ImportFromEPSG(6341)
            for name,res,size,nodata,value in [('fine',.5,4,-9999,10),('coarse',1,2,-999999,20),('last',1,2,-999999,30)]:
                p=Path(tmp)/(name+'.tif');paths.append(p)
                d=gdal.GetDriverByName('GTiff').Create(str(p),size,size,1,gdal.GDT_Float32)
                d.SetProjection(s.ExportToWkt());d.SetGeoTransform((518000,res,0,4253000,0,-res))
                z=np.full((size,size),value,dtype=np.float32)
                if name=='fine':z[1,1]=nodata
                d.GetRasterBand(1).SetNoDataValue(nodata);d.GetRasterBand(1).WriteArray(z);d=None
            z,ids,report=module.compose(paths,[518000,4252998,518002,4253000],.5,'EPSG:6341')
            self.assertEqual(z[1,1],20);self.assertEqual(ids[1,1],2)
            self.assertEqual(int((z==10).sum()),15);self.assertEqual(report[-1]['used_pixels'],0)

if __name__=='__main__':unittest.main()
