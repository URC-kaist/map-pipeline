#!/usr/bin/python3
"""Crop georeferenced RGB to the DEM footprint and generate standalone XYZ tiles."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

os.environ['PROJ_NETWORK'] = 'OFF'
from osgeo import gdal, ogr, osr
gdal.UseExceptions()
osr.UseExceptions()


def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()


def srs(value):
    s=osr.SpatialReference();s.SetFromUserInput(value)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def build(config_path, output):
    start=time.monotonic()
    config_path=Path(config_path).resolve();output=Path(output).resolve()
    c=json.loads(config_path.read_text())
    image=(config_path.parent/c['input']).resolve()
    dem_path=(config_path.parent/c['crop_dem']).resolve()
    if output.exists():raise ValueError('Choose a new output directory')
    if not 0<=c['minzoom']<=c['maxzoom']<=c['display_maxzoom']<=22:raise ValueError('Invalid zooms')
    if not 1<=c['processes']<=32:raise ValueError('Invalid worker count')
    rgb=gdal.Open(str(image));dem=gdal.Open(str(dem_path))
    if rgb.RasterCount!=3 or any(rgb.GetRasterBand(i).DataType!=gdal.GDT_Byte for i in [1,2,3]):
        raise ValueError('Expected Byte RGB source')
    if rgb.GetSpatialRef() is None or dem.GetSpatialRef() is None:raise ValueError('Missing CRS')
    gt=dem.GetGeoTransform()
    if gt[2] or gt[4]:raise ValueError('Expected north-up crop DEM')
    x0,y1=gt[0],gt[3];x1=x0+gt[1]*dem.RasterXSize;y0=y1+gt[5]*dem.RasterYSize
    ring=ogr.Geometry(ogr.wkbLinearRing)
    # Densify edges before projection; do not reinterpret EPSG:6341 as EPSG:26912.
    for a,b in [((x0,y1),(x1,y1)),((x1,y1),(x1,y0)),((x1,y0),(x0,y0)),((x0,y0),(x0,y1))]:
        for i in range(100):ring.AddPoint_2D(a[0]+(b[0]-a[0])*i/100,a[1]+(b[1]-a[1])*i/100)
    ring.AddPoint_2D(x0,y1);poly=ogr.Geometry(ogr.wkbPolygon);poly.AddGeometry(ring)
    dem_srs=dem.GetSpatialRef();dem_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geo=poly.Clone();geo.Transform(osr.CoordinateTransformation(dem_srs,srs('EPSG:4326')))
    west,east,south,north=geo.GetEnvelope();bounds=[west,south,east,north]
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.rgb-',dir=output.parent) as temp:
        result=Path(temp)/'result';result.mkdir();work=result/'work';work.mkdir()
        site=result/'site';tiles=site/'tiles/naip';tiles.mkdir(parents=True)
        gpkg=work/'crop.gpkg';ds=ogr.GetDriverByName('GPKG').CreateDataSource(str(gpkg))
        layer=ds.CreateLayer('crop',srs=dem_srs,geom_type=ogr.wkbPolygon)
        feature=ogr.Feature(layer.GetLayerDefn());feature.SetGeometry(poly);layer.CreateFeature(feature)
        feature=layer=ds=None
        resolution=2*math.pi*6378137/(256*2**c['maxzoom'])
        cropped=gdal.Warp(str(work/'cropped-3857.tif'),rgb,format='GTiff',
            dstSRS='EPSG:3857',cutlineDSName=str(gpkg),cropToCutline=True,
            xRes=resolution,yRes=resolution,targetAlignedPixels=True,
            dstAlpha=True,resampleAlg='bilinear',errorThreshold=0,
            creationOptions=['TILED=YES','COMPRESS=DEFLATE','BIGTIFF=IF_SAFER'])
        crop_info={'size':[cropped.RasterXSize,cropped.RasterYSize],
                   'geotransform':cropped.GetGeoTransform(),'crs':cropped.GetProjection()}
        cropped=None
        cmd=[sys.executable,'-m','osgeo_utils.gdal2tiles','--xyz','-p','mercator',
             '--tilesize=256','-z',f'{c["minzoom"]}-{c["maxzoom"]}','-r','average',
             f'--processes={c["processes"]}','-w','none','-n',
             'work/cropped-3857.tif','site/tiles/naip']
        env=dict(os.environ,GDAL_CACHEMAX='128',PROJ_NETWORK='OFF')
        with open(result/'generation.log','w') as log:
            subprocess.run(cmd,cwd=result,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        tilejson={'tilejson':'3.0.0','name':'MDRS NAIP 2024, DEM-footprint crop',
                  'tiles':['/tiles/naip/{z}/{x}/{y}.png'],'scheme':'xyz',
                  'minzoom':c['minzoom'],'maxzoom':c['maxzoom'],'tileSize':256,
                  'bounds':bounds,'attribution':'NAIP 2024 RGB / Utah raster portal'}
        (tiles/'tilejson.json').write_text(json.dumps(tilejson,indent=2)+'\n')
        outline={'type':'Feature','properties':{},'geometry':json.loads(geo.ExportToJson())}
        (site/'crop-outline.geojson').write_text(json.dumps(outline)+'\n')
        counts={str(z):len(list((tiles/str(z)).glob('*/*.png'))) for z in range(c['minzoom'],c['maxzoom']+1)}
        shutil.copyfile(__file__,result/'generate_source.py')
        manifest={'config':c,'input_sha256':sha(image),'crop_dem_sha256':sha(dem_path),
                  'source_crs':rgb.GetProjection(),'crop_crs':dem.GetProjection(),
                  'crop_outer_bounds':[x0,y0,x1,y1],'warped_crop':crop_info,
                  'bounds_wgs84':bounds,'gdal':gdal.VersionInfo('--version'),
                  'proj':f'{osr.GetPROJVersionMajor()}.{osr.GetPROJVersionMinor()}.{osr.GetPROJVersionMicro()}',
                  'proj_network':False,'tile_command':cmd,'tiles_per_zoom':counts,
                  'tile_bytes':sum(p.stat().st_size for p in tiles.rglob('*.png')),
                  'elapsed_seconds':time.monotonic()-start,
                  'datum_limit':'NAD83 to WGS84 operation nominal 4 m; NAD83(2011) to NAD83 is ballpark with installed grids. Not field-validated.',
                  'outputs':{str(p.relative_to(result)):sha(p) for p in sorted(result.rglob('*')) if p.is_file()}}
        (result/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        result.rename(output)
    print(json.dumps({k:manifest[k] for k in ['tiles_per_zoom','tile_bytes','elapsed_seconds']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path(__file__).parent/'config/naip.json')
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'output/mdrs-crop')
    a=p.parse_args();build(a.config,a.output)
