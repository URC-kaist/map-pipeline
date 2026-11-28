#!/usr/bin/python3
"""Optional deterministic OBJ/STL export, with a local georeferenced RGB texture."""
import argparse
import json
import os
from pathlib import Path
import struct
import tempfile

os.environ['PROJ_NETWORK'] = 'OFF'
import numpy as np
from osgeo import gdal

from pipeline import digest, NODATA


def export(result, output, stride=20, texture=None, formats='both'):
    result, output = Path(result).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new output directory')
    if stride < 1:
        raise ValueError('stride must be at least 1')
    meta = json.loads((result/'metadata.json').read_text())
    dem = gdal.Open(str(result/'dem.tif'))
    z = dem.ReadAsArray()
    valid = np.isfinite(z) & (z != NODATA)
    if not valid.any():
        raise ValueError('DEM contains no valid elevations')
    z0 = float(z[valid].min())
    gt = dem.GetGeoTransform()
    ax, ay = meta['anchor']['projected_m']
    h, w = z.shape
    # Include the final pixel center even when dimensions are not divisible by stride.
    rows = np.unique(np.r_[np.arange(0, h, stride), h-1])
    cols = np.unique(np.r_[np.arange(0, w, stride), w-1])
    rr, cc = np.meshgrid(rows, cols, indexing='ij')
    vertices = np.column_stack((
        (gt[0]+(cc+.5)*gt[1]-ax).ravel(),
        (gt[3]+(rr+.5)*gt[5]-ay).ravel(),
        np.where(valid[rr,cc], z[rr,cc]-z0, 0).ravel()))
    # Invalid vertices may be present but are never referenced by faces.
    uv = np.column_stack(((cc.ravel()+.5)/w, 1-(rr.ravel()+.5)/h))
    faces = []
    for i in range(len(rows)-1):
        for j in range(len(cols)-1):
            # Check the ENTIRE skipped quad, not just its four sampled corners.
            if not valid[rows[i]:rows[i+1]+1, cols[j]:cols[j+1]+1].all():
                continue
            a = i*len(cols)+j
            b = a+len(cols)
            faces.extend([(a,b,b+1), (a,b+1,a+1)])
    if not faces:
        raise ValueError('No fully valid mesh quads at this stride')
    # Explicit smooth normals are required by OGRE2's mesh conversion path.
    triangles = np.asarray(faces)
    face_normals = np.cross(vertices[triangles[:, 1]]-vertices[triangles[:, 0]],
                            vertices[triangles[:, 2]]-vertices[triangles[:, 0]])
    normals = np.zeros_like(vertices)
    for corner in range(3):
        np.add.at(normals, triangles[:, corner], face_normals)
    lengths = np.linalg.norm(normals, axis=1)
    normals[lengths > 0] /= lengths[lengths > 0, None]
    normals[lengths == 0] = [0, 0, 1]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.mesh-', dir=output.parent) as tmp:
        work = Path(tmp)/'result'
        work.mkdir()
        texture_info = None
        if texture:
            texture = Path(texture).resolve()
            rgb = gdal.Open(str(texture))
            if rgb.RasterCount != 3 or rgb.GetSpatialRef() is None:
                raise ValueError('Texture input must be a three-band georeferenced RGB raster')
            if any(rgb.GetRasterBand(i).DataType != gdal.GDT_Byte for i in range(1,4)):
                raise ValueError('Texture input must use 8-bit RGB samples')
            scale = min(1, 2048/max(w,h))
            extent = [gt[0],gt[3]+h*gt[5],gt[0]+w*gt[1],gt[3]]
            warped = gdal.Warp('', rgb, format='MEM', dstSRS=dem.GetProjection(),
                               outputBounds=extent, width=max(1,round(w*scale)),
                               height=max(1,round(h*scale)), resampleAlg='bilinear',
                               dstAlpha=True, errorThreshold=0)
            gdal.SetConfigOption('GDAL_PAM_ENABLED','NO')
            gdal.Translate(str(work/'texture.png'), warped, format='PNG')
            texture_info = {'input': str(texture), 'sha256': digest(texture),
                            'size': [warped.RasterXSize,warped.RasterYSize],
                            'registration': 'warped to the DEM CRS and outer extent; UVs at pixel centers',
                            'datum_accuracy': 'depends on installed PROJ operations; not field-validated'}
        if formats in ('obj','both'):
            with open(work/'terrain.obj','w') as f:
                if texture:
                    f.write('mtllib terrain.mtl\nusemtl aerial\n')
                for v in vertices:
                    f.write('v %.6f %.6f %.6f\n' % tuple(v))
                if texture:
                    for u,v in uv:
                        f.write(f'vt {u:.9f} {v:.9f}\n')
                for normal in normals:
                    f.write('vn %.9f %.9f %.9f\n' % tuple(normal))
                for face in faces:
                    ids = [i+1 for i in face]
                    f.write('f '+' '.join(f'{i}/{i}/{i}' if texture else f'{i}//{i}' for i in ids)+'\n')
            if texture:
                (work/'terrain.mtl').write_text('newmtl aerial\nKd 1 1 1\nmap_Kd texture.png\n')
        if formats in ('stl','both'):
            with open(work/'terrain.stl','wb') as f:
                f.write(b'cartographer sampled DEM mesh'.ljust(80,b'\0'))
                f.write(struct.pack('<I',len(faces)))
                for face in faces:
                    tri = vertices[list(face)]
                    normal = np.cross(tri[1]-tri[0],tri[2]-tri[0])
                    normal /= np.linalg.norm(normal)
                    f.write(struct.pack('<12fH',*normal,*tri.ravel(),0))
        record = {
            'dem_sha256': digest(result/'dem.tif'),
            'metadata_sha256': digest(result/'metadata.json'), 'script_sha256': digest(__file__),
            'stride_pixels': stride, 'vertices': len(vertices), 'triangles': len(faces),
            'local_frame': meta['local_frame'], 'anchor': meta['anchor'],
            'z_offset_m': z0, 'placement': 'x/y already in local projected frame; add z_offset_m to restore source elevations',
            'missing_terrain': 'no face crosses any invalid full-resolution DEM sample in its quad',
            'texture': texture_info,
            'outputs': {p.name:digest(p) for p in sorted(work.iterdir())},
        }
        (work/'mesh.json').write_text(json.dumps(record,indent=2)+'\n')
        work.rename(output)
    print(f'Created {output}: {len(faces)} triangles')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('result',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stride',type=int,default=20,help='Grid sampling interval; larger means fewer faces')
    p.add_argument('--texture',type=Path,help='Local georeferenced three-band RGB TIFF')
    p.add_argument('--format',choices=['obj','stl','both'],default='both')
    args = p.parse_args()
    try:
        export(args.result,args.output,args.stride,args.texture,args.format)
    except (ValueError,RuntimeError) as e:
        p.exit(1,f'Mesh export failed: {e}\n')
