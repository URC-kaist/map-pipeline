#!/usr/bin/python3
"""Draw MDRS, the approximate URC rule area, and N/E/S/W on a slope-image copy."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile

from osgeo import gdal,osr
from PIL import Image,ImageDraw,ImageFont

RULE_BOUNDS=(-110.786,38.411,-110.768,38.425)  # W,S,E,N; URC 2027 1.e.xiii


def rule_outline(metadata,bounds=RULE_BOUNDS):
    west,south,east,north=bounds
    if not all(math.isfinite(v) for v in bounds) or not (-180<=west<east<=180 and -90<south<north<90):
        raise ValueError('Invalid geographic rule-area bounds')
    source=osr.SpatialReference();source.ImportFromEPSG(4326)
    target=osr.SpatialReference();target.SetFromUserInput(metadata['projected_crs_wkt'])
    for s in [source,target]:s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform=osr.CoordinateTransformation(source,target)
    inverse=gdal.InvGeoTransform(metadata['geotransform'])
    if inverse is None:raise ValueError('Non-invertible pixel transform')
    corners=[(west,north),(east,north),(east,south),(west,south),(west,north)]
    pixels=[]
    for a,b in zip(corners,corners[1:]):
        for i in range(100):
            lon=a[0]+(b[0]-a[0])*i/100;lat=a[1]+(b[1]-a[1])*i/100
            x,y,_=transform.TransformPoint(lon,lat)
            pixels.append(list(gdal.ApplyGeoTransform(inverse,x,y)))
    pixels.append(pixels[0])
    w,h=metadata['size'];xs=[p[0] for p in pixels];ys=[p[1] for p in pixels]
    return {'source':'URC 2027 rule 1.e.xiii; approximate opposite corners, not a surveyed parcel boundary',
            'bounds_wgs84':list(bounds),'pixel_outer_edge_coordinates':pixels,
            'fully_inside_image':all(0<=x<w and 0<=y<h for x,y in pixels),
            'intersects_image_bounds':max(xs)>=0 and min(xs)<w and max(ys)>=0 and min(ys)<h}


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def locate(metadata,latitude,longitude):
    source=osr.SpatialReference();source.ImportFromEPSG(4326)
    target=osr.SpatialReference();target.SetFromUserInput(metadata['projected_crs_wkt'])
    for s in [source,target]:s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform=osr.CoordinateTransformation(source,target)
    inverse=gdal.InvGeoTransform(metadata['geotransform'])
    def pixel(lon,lat):
        x,y,_=transform.TransformPoint(lon,lat)
        return gdal.ApplyGeoTransform(inverse,x,y)
    x,y,_=transform.TransformPoint(longitude,latitude)
    col,row=pixel(longitude,latitude)
    w,h=metadata['size']
    if not (0<=col<w and 0<=row<h):raise ValueError('Requested location is outside the image footprint')
    # Local geographic directions, not an assumption that grid-up equals true north.
    delta=.0001
    directions={}
    for label,lon,lat in [('N',longitude,latitude+delta),('E',longitude+delta,latitude),
                          ('S',longitude,latitude-delta),('W',longitude-delta,latitude)]:
        a,b=pixel(lon,lat);dx,dy=a-col,b-row;length=math.hypot(dx,dy)
        if not length:raise ValueError('Degenerate compass transformation')
        directions[label]=[dx/length,dy/length]
    return {'latitude':latitude,'longitude':longitude,'projected_m':[x,y],
            'pixel_outer_edge_coordinates':[col,row],'direction_unit_vectors':directions}


def annotate(result,output=None,latitude=38.4053,longitude=-110.7900,max_size=None,include_rule=True):
    result=Path(result).resolve();source=result/'slope.png'
    output=Path(output).resolve() if output else result/'slope_annotated.png'
    sidecar=output.with_suffix('.json')
    if output.suffix.lower()!='.png':raise ValueError('Output must use a .png extension')
    if output==source or output.exists() or sidecar.exists():raise ValueError('Choose a new output filename; sources and existing annotations are never overwritten')
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -89.99<latitude<89.99 or not -180<=longitude<=180:
        raise ValueError('Coordinates must be finite longitude/latitude, away from the poles')
    if max_size is not None and max_size<256:raise ValueError('max-size must be at least 256 pixels')
    metadata=json.loads((result/'metadata.json').read_text())
    position=locate(metadata,latitude,longitude)
    region=rule_outline(metadata) if include_rule else None
    # The slope image is large but expected (~88 MP). Do not disable Pillow's
    # decompression checks globally; reject images inconsistent with metadata.
    with Image.open(source) as original:
        if list(original.size)!=metadata['size']:raise ValueError('Image dimensions differ from metadata')
        image=original.convert('RGBA')
    original_size=image.size
    if max_size:image.thumbnail((max_size,max_size),getattr(Image,'Resampling',Image).NEAREST)
    w,h=image.size;sx=w/original_size[0];sy=h/original_size[1]
    col,row=position['pixel_outer_edge_coordinates'];point=(col*sx-.5,row*sy-.5)
    unit=max(1,min(w,h)/1200);font_size=max(12,round(18*unit))
    try:font=ImageFont.truetype('DejaVuSans.ttf',font_size)
    except OSError:font=ImageFont.load_default()
    draw=ImageDraw.Draw(image)
    def text_box(x,y,text):
        box=draw.multiline_textbbox((0,0),text,font=font,spacing=round(4*unit))
        tw,th=box[2]-box[0],box[3]-box[1];pad=round(6*unit)
        x=max(pad,min(x,w-tw-2*pad));y=max(pad,min(y,h-th-2*pad))
        draw.rectangle((x-pad,y-pad,x+tw+pad,y+th+2*pad),fill=(15,20,28,230))
        draw.multiline_text((x,y),text,font=font,fill='white',spacing=round(4*unit))
    if region and region['intersects_image_bounds']:
        points=[(x*sx-.5,y*sy-.5) for x,y in region['pixel_outer_edge_coordinates']]
        # Outline only: retain the visible terrain inside the approximate area.
        draw.line(points,fill='black',width=max(4,round(6*unit)),joint='curve')
        draw.line(points,fill='#ffd84d',width=max(2,round(3*unit)),joint='curve')
        text_box(min(p[0] for p in points),min(p[1] for p in points)-62*unit,
                 'URC 2027 rule 1.e.xiii\nApproximate rule-book area')
        for label,index in [('NE',100),('SW',300)]:
            x,y=points[index]
            draw.text((x+7*unit,y+7*unit),label,font=font,fill='#ffd84d',
                      stroke_width=max(1,round(unit)),stroke_fill='black')
    radius=round(8*unit);px,py=point
    draw.ellipse((px-radius,py-radius,px+radius,py+radius),fill='#ff394f',outline='white',width=max(1,round(2*unit)))
    arm=round(17*unit)
    draw.line((px-arm,py,px+arm,py),fill='#ff394f',width=max(1,round(2*unit)))
    draw.line((px,py-arm,px,py+arm),fill='#ff394f',width=max(1,round(2*unit)))
    text_box(px+24*unit,py+18*unit,f'MDRS\n{latitude:.4f}, {longitude:.4f}')
    # Compass is a corner legend oriented using the geographic tangent at MDRS.
    reach=50*unit;cx=w-105*unit;cy=105*unit
    draw.rectangle((cx-85*unit,cy-85*unit,cx+85*unit,cy+105*unit),fill=(15,20,28,230))
    for label,(dx,dy) in position['direction_unit_vectors'].items():
        dx,dy=dx*sx,dy*sy;length=math.hypot(dx,dy);dx/=length;dy/=length
        ex,ey=cx+reach*dx,cy+reach*dy;color='#ff6575' if label=='N' else 'white'
        draw.line((cx,cy,ex,ey),fill=color,width=max(1,round(2*unit)))
        size=7*unit
        draw.polygon([(ex,ey),(ex-size*dx+size*.5*dy,ey-size*dy-size*.5*dx),
                      (ex-size*dx-size*.5*dy,ey-size*dy+size*.5*dx)],fill=color)
        tx,ty=cx+(reach+17*unit)*dx,cy+(reach+17*unit)*dy
        draw.text((tx,ty),label,font=font,fill=color,anchor='mm')
    draw.text((cx,cy+84*unit),'True N/E/S/W',font=font,fill='white',anchor='mm')
    text_box(20*unit,h-65*unit,'Annotated review copy - not a navigation input')
    record={'source':str(source),'source_sha256':sha(source),
            'metadata_sha256':sha(result/'metadata.json'),'source_size':list(original_size),
            'output_size':list(image.size),'marker':position,'marker_output_pixel':point,
            'rule_region':region,
            'coordinate_input':'WGS84 longitude/latitude supplied by user (Google Maps)',
            'compass':'geographic cardinal tangents at the marker; includes projection convergence',
            'limits':'Approximate datum operation and supplied coordinate precision; not a surveyed position. Annotation is visual only.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.annotate-',dir=output.parent) as temp:
        candidate=Path(temp)/'image.png';image.save(candidate,format='PNG')
        record['output_sha256']=sha(candidate)
        info=Path(temp)/'image.json';info.write_text(json.dumps(record,indent=2)+'\n')
        candidate.rename(output);info.rename(sidecar)
    print(f'Created {output}; MDRS source pixel ({col:.2f}, {row:.2f})')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('result',type=Path,help='Terrain result directory with slope.png and metadata.json')
    p.add_argument('--output',type=Path)
    p.add_argument('--latitude',type=float,default=38.4053)
    p.add_argument('--longitude',type=float,default=-110.7900)
    p.add_argument('--max-size',type=int,help='Optional review thumbnail; default preserves source dimensions')
    p.add_argument('--no-rule-region',action='store_true',help='Omit the approximate URC 2027 rule-area outline')
    a=p.parse_args()
    try:annotate(a.result,a.output,a.latitude,a.longitude,a.max_size,not a.no_rule_region)
    except (ValueError,RuntimeError) as e:p.exit(1,f'Annotation failed: {e}\n')
