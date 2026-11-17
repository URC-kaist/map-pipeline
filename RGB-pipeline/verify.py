#!/usr/bin/python3
"""Verify projection arithmetic, cropped pixels, every tile, manifest and HTTP routes."""
import argparse
import io
import json
import math
from pathlib import Path
import subprocess
import threading
from urllib.request import urlopen

import numpy as np
from osgeo import gdal,osr
from PIL import Image
from generate import srs,sha
from serve import create_server


def run(output,report):
    output=Path(output).resolve();root=Path(__file__).resolve().parent
    m=json.loads((output/'manifest.json').read_text())
    for name,h in m['outputs'].items():assert sha(output/name)==h,name
    crop=gdal.Open(str(output/'work/cropped-3857.tif'));gt=crop.GetGeoTransform()
    assert crop.GetSpatialRef().IsSame(srs('EPSG:3857'))
    assert crop.RasterCount==4
    controls=[];worst=0
    src=srs('EPSG:26912');merc=srs('EPSG:3857');geo=srs('EPSG:4326')
    forward=osr.CoordinateTransformation(src,merc);inverse=osr.CoordinateTransformation(merc,src)
    togeo=osr.CoordinateTransformation(src,geo)
    dem_to_src=osr.CoordinateTransformation(srs('EPSG:6341'),src)
    tiles=output/'site/tiles/naip'
    for e,n in [(518250,4248500),(519000,4250500),(520000,4251500),(521000,4252500)]:
        a,b,_=dem_to_src.TransformPoint(e,n)
        x,y,_=forward.TransformPoint(a,b)
        aa,bb,_=inverse.TransformPoint(x,y)
        err=math.hypot(a-aa,b-bb);worst=max(worst,err);assert err<1e-6
        lon,lat,_=togeo.TransformPoint(a,b)
        manual_x=6378137*math.radians(lon)
        manual_y=6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2))
        assert math.hypot(x-manual_x,y-manual_y)<1e-6
        col,row=gdal.ApplyGeoTransform(gdal.InvGeoTransform(gt),x,y)
        col,row=math.floor(col),math.floor(row)
        sample=crop.ReadAsArray(col,row,1,1)[:,0,0]
        assert sample[3]>0
        z=m['config']['maxzoom'];world=256*2**z
        px=(lon+180)/360*world
        py=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*world
        tx,ty=int(px//256),int(py//256);ix,iy=int(px%256),int(py%256)
        path=tiles/str(z)/str(tx)/(str(ty)+'.png')
        rgba=np.asarray(Image.open(path).convert('RGBA'))[iy,ix]
        delta=int(np.abs(rgba.astype(int)-sample.astype(int)).max());assert delta<=2,(path,delta)
        controls.append({'dem_utm':[e,n],'longitude_latitude':[lon,lat],
                         'mercator':[x,y],'xyz':[z,tx,ty],'pixel':[ix,iy],
                         'crop_rgba':sample.tolist(),'tile_rgba':rgba.tolist(),
                         'maximum_channel_difference':delta})
    # The expanded two-image mosaic must cover the former eastern imagery gap.
    x,y,_=osr.CoordinateTransformation(srs('EPSG:6341'),merc).TransformPoint(521950,4250500)
    col,row=gdal.ApplyGeoTransform(gdal.InvGeoTransform(gt),x,y)
    assert crop.GetRasterBand(4).ReadAsArray(int(col),int(row),1,1)[0,0]==255
    actual={};alpha_tiles=0
    for z in range(m['config']['minzoom'],m['config']['maxzoom']+1):
        files=list((tiles/str(z)).glob('*/*.png'));actual[str(z)]=len(files)
        assert files
        for p in files:
            with Image.open(p) as im:
                assert im.size==(256,256)
                im.load()
                if im.convert('RGBA').getchannel('A').getextrema()[0]<255:alpha_tiles+=1
    assert actual==m['tiles_per_zoom']
    assert not (tiles/'19').exists()
    tj=json.loads((tiles/'tilejson.json').read_text())
    assert (tj['minzoom'],tj['maxzoom'],tj['scheme'])==(14,18,'xyz')
    has_viewer=(output/'site/index.html').is_file()
    if has_viewer:
        html=(output/'site/index.html').read_text()
        assert 'https://' not in html and 'http://' not in html
    http_checks=[]
    with create_server(output/'site',port=0) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            tile=next((tiles/'18').glob('*/*.png')).relative_to(output/'site').as_posix()
            routes=['/tiles/naip/tilejson.json','/crop-outline.geojson','/'+tile]
            if has_viewer:routes+=['/','/vendor/maplibre-gl.js','/vendor/maplibre-gl.css']
            for route in routes:
                with urlopen(f'http://127.0.0.1:{server.server_port}{route}') as response:
                    assert response.status==200;body=response.read()
                    if route.endswith('.png'):assert Image.open(io.BytesIO(body)).size==(256,256)
                    http_checks.append({'route':route,'status':response.status,'bytes':len(body)})
        finally:server.shutdown();thread.join()
    ops={}
    for a,b in [('26912','3857'),('6341','26912'),('6341','3857')]:
        ops[a+'->'+b]=subprocess.check_output(['projinfo','-s','EPSG:'+a,'-t','EPSG:'+b,'--summary'],text=True,stderr=subprocess.STDOUT)
    result={'result':'passed','tile_counts':actual,'tiles_with_transparency':alpha_tiles,
            'controls':controls,'roundtrip_max_m':worst,'http':http_checks,
            'operations':ops,'former_eastern_gap_alpha':255,
            'limits':'Numerical/HTTP verification, not surveyed alignment or live Nav2 /toLL validation. Browser verification is recorded separately in evidence/browser.json.'}
    Path(report).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['result','tile_counts','roundtrip_max_m','tiles_with_transparency']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--report',type=Path,default=Path(__file__).parent/'evidence/verification.json')
    a=p.parse_args();run(a.output,a.report)
