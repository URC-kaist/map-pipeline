#!/usr/bin/python3
"""Mosaic verified DEM sources by priority; retain provenance and true NoData."""
import json
from pathlib import Path
import numpy as np
from osgeo import gdal,osr
from download_sources import checksum
from prepare_sources import prepare

gdal.UseExceptions()

def compose(paths,bounds,resolution,crs):
    w=round((bounds[2]-bounds[0])/resolution);h=round((bounds[3]-bounds[1])/resolution)
    z=np.full((h,w),-9999,dtype=np.float32);ids=np.zeros((h,w),np.uint8);records=[]
    for i,path in enumerate(paths,1):
        source=gdal.Open(str(path));horizontal=source.GetSpatialRef().Clone();horizontal.DemoteTo2D()
        opts=dict(format='MEM',srcSRS=horizontal.ExportToWkt(),dstSRS=crs,outputBounds=bounds,width=w,height=h,dstNodata=-9999,outputType=gdal.GDT_Float32,errorThreshold=0)
        sample=gdal.Warp('',source,resampleAlg='bilinear',**opts).ReadAsArray()
        valid=gdal.Warp('',source,resampleAlg='near',**opts).ReadAsArray()!=-9999
        valid &= np.isfinite(sample)&(sample!=-9999)
        take=(ids==0)&valid
        # Summarize overlaps for review; this does not establish vertical datum equivalence.
        overlap=valid&(ids!=0)
        delta=sample[overlap]-z[overlap]
        records.append({'id':i,'path':str(path),'sha256':checksum(path),'native_resolution':source.GetGeoTransform()[1],
                        'crs_wkt':source.GetProjection(),'used_pixels':int(take.sum()),
                        'overlap_delta_median_m':float(np.median(delta)) if delta.size else None,
                        'overlap_abs_delta_p95_m':float(np.percentile(np.abs(delta),95)) if delta.size else None})
        z[take]=sample[take];ids[take]=i
    return z,ids,records

def main():
    root=Path(__file__).resolve().parent;c=json.loads((root/'map-region.json').read_text())
    folder=root/'Lidar';out=folder/'bare_earth_expanded_0p5m.tif'
    if out.exists():raise ValueError('Expanded mosaic exists; preserve it or choose a new output before rebuilding')
    prepare(root,root/'sources.json')
    entries=json.loads((root/'sources.json').read_text())['sources']
    paths=sorted(root/Path(e['path']).with_suffix('.tif') for e in entries if e['path'].startswith('Lidar/'))
    # Manifest order is 2018, 2020, 2022: preserve earlier/finer valid data; newer sources only fill holes.
    z,ids,records=compose(paths,c['bounds'],c['resolution_m'],c['crs'])
    for record in records:record['path']=str(Path(record['path']).relative_to(root))
    s=osr.SpatialReference();s.SetFromUserInput(c['crs']);b=c['bounds'];res=c['resolution_m'];h,w=z.shape
    for p,data,kind in [(out,z,gdal.GDT_Float32),(folder/'source-id.tif',ids,gdal.GDT_Byte)]:
        d=gdal.GetDriverByName('GTiff').Create(str(p),w,h,1,kind,['TILED=YES','COMPRESS=DEFLATE'])
        d.SetProjection(s.ExportToWkt());d.SetGeoTransform((b[0],res,0,b[3],0,-res))
        d.GetRasterBand(1).SetNoDataValue(-9999 if kind==gdal.GDT_Float32 else 0)
        if kind==gdal.GDT_Float32:d.GetRasterBand(1).SetUnitType('metre')
        d.GetRasterBand(1).WriteArray(data);d=None
    report={'bounds':b,'size':[w,h],'resolution_m':res,'crs':c['crs'],'priority':'2018 valid first, then 2020 holes, then 2022 holes',
            'nodata_pixels':int((ids==0).sum()),'sources':records,'vertical_datum':'Provider heights retained; 2018/2020 vertical metadata unestablished, 2022 advertises NAVD88 Geoid18. No vertical correction; overlap statistics are diagnostic, not datum proof.'}
    (folder/'mosaic-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
if __name__=='__main__':main()
