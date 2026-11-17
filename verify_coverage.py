#!/usr/bin/python3
"""Check complete operating AOI DEM, terrain-cost and RGB alpha coverage."""
from pathlib import Path
import json
import numpy as np
from osgeo import gdal,ogr,osr
root=Path(__file__).resolve().parent
region=json.loads((root/'map-region.json').read_text())
w,s,e,n=region['operating_aoi_wgs84'];ring=ogr.Geometry(ogr.wkbLinearRing)
for a,b in [((w,s),(e,s)),((e,s),(e,n)),((e,n),(w,n)),((w,n),(w,s))]:
 for i in range(100):ring.AddPoint_2D(a[0]+(b[0]-a[0])*i/100,a[1]+(b[1]-a[1])*i/100)
ring.AddPoint_2D(w,s);polygon=ogr.Geometry(ogr.wkbPolygon);polygon.AddGeometry(ring)
geo=osr.SpatialReference();geo.ImportFromEPSG(4326);geo.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
files={'dem':('Lidar/bare_earth_expanded_0p5m.tif',1,-9999),
       'cost_validity':('Lidar-pipeline/output/mdrs-expanded/validity.tif',1,0),
       'rgb_alpha':('RGB-pipeline/output/mdrs-expanded/work/cropped-3857.tif',4,0)}
report={'aoi_wgs84':[w,s,e,n],'map_region':region,'checks':{}}
for name,(path,band,nodata) in files.items():
 ds=gdal.Open(str(root/path));target=ds.GetSpatialRef();target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
 transform=osr.CoordinateTransformation(geo,target);poly=polygon.Clone();poly.Transform(transform)
 vectors=ogr.GetDriverByName('Memory').CreateDataSource('');layer=vectors.CreateLayer('aoi',srs=target);f=ogr.Feature(layer.GetLayerDefn());f.SetGeometry(poly);layer.CreateFeature(f)
 mask=gdal.GetDriverByName('MEM').Create('',ds.RasterXSize,ds.RasterYSize,1,gdal.GDT_Byte)
 mask.SetGeoTransform(ds.GetGeoTransform());mask.SetProjection(ds.GetProjection());gdal.RasterizeLayer(mask,[1],layer,burn_values=[1])
 inside=mask.ReadAsArray().astype(bool);values=ds.GetRasterBand(band).ReadAsArray();bad=inside&((values==nodata)|~np.isfinite(values))
 assert not bad.any(),(name,int(bad.sum()))
 points=[]
 for lon,lat in [(w,s),(e,n)]:
  x,y,_=transform.TransformPoint(lon,lat);col,row=gdal.ApplyGeoTransform(gdal.InvGeoTransform(ds.GetGeoTransform()),x,y)
  value=float(values[int(row),int(col)]);assert value!=nodata;points.append({'latitude':lat,'longitude':lon,'value':value})
 report['checks'][name]={'cells_inside_aoi':int(inside.sum()),'missing_cells':int(bad.sum()),'corners':points}
(root/'docs/expanded-coverage-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
