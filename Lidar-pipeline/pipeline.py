#!/usr/bin/python3
"""Offline georeferenced DEM -> terrain features -> Nav2 raw map.

All paths in a config are relative to the config, never the working directory.
Outputs are published as a new directory only after a complete successful run.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

os.environ['PROJ_NETWORK'] = 'OFF'
import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
osr.UseExceptions()
NODATA = -9999.0
CO = ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=IF_SAFER']


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def crs(text):
    s = osr.SpatialReference()
    s.SetFromUserInput(text)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def horn(z, resolution):
    """Interior cells only: derivatives positive toward east and north.

    Unknown in any of the nine input cells makes the output cell unknown.
    Input uses NaN for unknown. Output excludes the 1-cell halo on all sides.
    """
    valid = np.ones((z.shape[0]-2, z.shape[1]-2), dtype=bool)
    for y in range(3):
        for x in range(3):
            valid &= np.isfinite(z[y:y+valid.shape[0], x:x+valid.shape[1]])
    dx = (z[:-2, 2:] + 2*z[1:-1, 2:] + z[2:, 2:]
          - z[:-2, :-2] - 2*z[1:-1, :-2] - z[2:, :-2]) / (8*resolution)
    dy = (z[:-2, :-2] + 2*z[:-2, 1:-1] + z[:-2, 2:]
          - z[2:, :-2] - 2*z[2:, 1:-1] - z[2:, 2:]) / (8*resolution)
    return np.where(valid, dx, np.nan), np.where(valid, dy, np.nan), valid


def occupancy(magnitude, valid, full_deg):
    # A slope-based traversal cost, not a measured occupancy probability.
    result = np.full(magnitude.shape, 255, dtype=np.uint8)
    result[valid] = np.rint(100*np.clip(
        magnitude[valid] / math.tan(math.radians(full_deg)), 0, 1)).astype(np.uint8)
    return result


def create_tif(path, width, height, bands, dtype, gt, projection, nodata=None):
    opts = CO + (['PREDICTOR=3'] if dtype == gdal.GDT_Float32 else [])
    ds = gdal.GetDriverByName('GTiff').Create(str(path), width, height, bands, dtype, opts)
    ds.SetGeoTransform(gt)
    ds.SetProjection(projection)
    if nodata is not None:
        for i in range(1, bands+1):
            ds.GetRasterBand(i).SetNoDataValue(nodata)
    return ds


def source_dem(config, config_dir, work):
    """Accept a projected DEM, or explicitly configured ground-class LAZ/LAS."""
    source = (config_dir / config['input']).resolve()
    if not source.is_file():
        raise ValueError(f'Missing input: {source}; build the DEM mosaic first')
    info = {'path': config['input'], 'sha256': digest(source)}
    if source.suffix.lower() not in ('.laz', '.las'):
        return source, info
    if not shutil.which('pdal'):
        raise ValueError('LAS/LAZ inputs require PDAL')
    pc = config['pointcloud']
    if pc['ground_classes'] != [2]:
        raise ValueError('This bare-earth rasterizer accepts ground class 2 only')
    cloud_crs = crs(pc['crs'])
    if not cloud_crs.IsProjected() or abs(cloud_crs.GetLinearUnits()-1) > 1e-9:
        raise ValueError('Point-cloud rasterization requires a projected metre CRS')
    resolution = float(pc['resolution_m'])
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError('Invalid point-cloud resolution')
    output = work/'source_dem.tif'
    stages = {'pipeline': [
        {'type': 'readers.las', 'filename': str(source), 'override_srs': pc['crs']},
        {'type': 'filters.range', 'limits': 'Classification[2:2]'},
        {'type': 'writers.gdal', 'filename': output.name, 'resolution': resolution,
         'output_type': 'mean', 'data_type': 'float', 'nodata': NODATA,
         'gdalopts': 'COMPRESS=DEFLATE,TILED=YES'}]}
    path = work/'pdal-pipeline.json'
    path.write_text(json.dumps(stages, indent=2)+'\n')
    r = subprocess.run(['pdal', 'pipeline', path.name], cwd=work, capture_output=True, text=True)
    (work/'pdal.log').write_text(r.stdout+r.stderr)
    r.check_returncode()
    info['pdal_version'] = subprocess.check_output(['pdal', '--version'], text=True).strip()
    info['pointcloud_crs_override'] = pc['crs']
    return output, info


def validate_config(config):
    target = crs(config['target_crs'])
    if not target.IsProjected() or abs(target.GetLinearUnits()-1) > 1e-9:
        raise ValueError('Target CRS must be projected in metres')
    if target.IsCompound():
        raise ValueError('Vertical conversion is outside this horizontal raster pipeline')
    # Topocentric alone is a 3D conversion, not a valid geographic map projection.
    if 'topocentric' in config['target_crs'].lower():
        raise ValueError('Use a tested projected CRS; topocentric requires a separate 3D design')
    bounds = list(map(float, config['bounds']))
    res = float(config['resolution_m'])
    if len(bounds) != 4 or not all(math.isfinite(x) for x in bounds+[res]):
        raise ValueError('Bounds and resolution must be finite')
    if res <= 0 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError('Invalid bounds or resolution')
    width, height = (bounds[2]-bounds[0])/res, (bounds[3]-bounds[1])/res
    if any(abs(x-round(x)) > 1e-6 for x in [width, height]) or min(width, height) < 3:
        raise ValueError('Bounds must span whole pixels and at least 3 cells per side')
    if config['resampling'] not in ['near', 'bilinear', 'cubic', 'cubicspline']:
        raise ValueError('Unsupported resampling method')
    deg = float(config['full_cost_slope_deg'])
    if not math.isfinite(deg) or not 0 < deg < 90:
        raise ValueError('full_cost_slope_deg must be between 0 and 90')
    anchor = config['anchor']
    if not math.isfinite(anchor['longitude']) or not math.isfinite(anchor['latitude']):
        raise ValueError('Invalid anchor')
    anchor_crs = crs(anchor['crs'])
    if not anchor_crs.IsGeographic():
        raise ValueError('Anchor CRS must be geographic')
    return target, bounds, res, int(round(width)), int(round(height))


def build(config_path, output):
    config_path = Path(config_path).resolve()
    output = Path(output).resolve()
    config = json.loads(config_path.read_text())
    target, bounds, res, width, height = validate_config(config)
    if output.exists():
        raise ValueError(f'Output already exists; choose a new directory: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.terrain-', dir=output.parent) as temp:
        work = Path(temp)/'result'
        work.mkdir()
        source, input_info = source_dem(config, config_path.parent, work)
        src = gdal.Open(str(source))
        if src.RasterCount != 1 or src.GetSpatialRef() is None:
            raise ValueError('Input must be a single-band georeferenced elevation raster')
        # Explicitly retain band elevations: this is not a vertical transformation.
        horizontal = src.GetSpatialRef().Clone()
        if horizontal.IsCompound():
            horizontal.DemoteTo2D()
        if not horizontal.IsProjected() or abs(horizontal.GetLinearUnits()-1) > 1e-9:
            raise ValueError('Input must use a projected metre horizontal CRS')
        if src.GetRasterBand(1).GetUnitType() not in ('', 'metre', 'meter', 'm'):
            raise ValueError('Elevation must be in metres')
        warp_opts = dict(format='GTiff', srcSRS=horizontal.ExportToWkt(),
                         dstSRS=target.ExportToWkt(), outputBounds=bounds,
                         width=width, height=height, outputType=gdal.GDT_Float32,
                         dstNodata=NODATA, resampleAlg=config['resampling'],
                         errorThreshold=0, multithread=False,
                         creationOptions=CO+['PREDICTOR=3'])
        dem = gdal.Warp(str(work/'dem.tif'), src, **warp_opts)
        dem.GetRasterBand(1).SetUnitType('metre')
        dem.FlushCache()
        gt = dem.GetGeoTransform()
        min_z, max_z = dem.GetRasterBand(1).ComputeRasterMinMax(False)
        if not all(math.isfinite(z) for z in [min_z, max_z]) or min_z == NODATA:
            raise ValueError('No finite valid elevations in requested bounds')
        projection = dem.GetProjection()
        angle_ds = create_tif(work/'slope_degrees.tif', width, height, 1,
                              gdal.GDT_Float32, gt, projection, NODATA)
        angle_ds.GetRasterBand(1).SetUnitType('degree')
        mag_ds = create_tif(work/'slope_magnitude.tif', width, height, 1,
                            gdal.GDT_Float32, gt, projection, NODATA)
        valid_ds = create_tif(work/'validity.tif', width, height, 1,
                              gdal.GDT_Byte, gt, projection)
        costs = create_tif(Path(temp)/'cost.tif', width, height, 1,
                           gdal.GDT_Byte, gt, projection)
        previews = create_tif(Path(temp)/'previews.tif', width, height, 7,
                              gdal.GDT_Byte, gt, projection)
        histogram = np.zeros(256, dtype=np.int64)
        valid_elevations = 0
        for row in range(0, height, 256):
            rows = min(256, height-row)
            start, end = max(0, row-1), min(height, row+rows+1)
            z = dem.ReadAsArray(0, start, width, end-start).astype(np.float32)
            z[(z == NODATA) | ~np.isfinite(z)] = np.nan
            z = np.pad(z, ((int(row == 0), int(row+rows == height)), (1, 1)),
                       mode='constant', constant_values=np.nan)
            center = z[1:-1, 1:-1]
            elev_valid = np.isfinite(center)
            valid_elevations += int(elev_valid.sum())
            dx, dy, valid = horn(z, res)
            mag = np.hypot(dx, dy)
            degrees = np.degrees(np.arctan(mag))
            angle_ds.GetRasterBand(1).WriteArray(np.where(valid, degrees, NODATA), 0, row)
            mag_ds.GetRasterBand(1).WriteArray(np.where(valid, mag, NODATA), 0, row)
            valid_ds.GetRasterBand(1).WriteArray(valid.astype(np.uint8)*255, 0, row)
            cost = occupancy(mag, valid, config['full_cost_slope_deg'])
            histogram += np.bincount(cost.ravel(), minlength=256)
            costs.GetRasterBand(1).WriteArray(cost, 0, row)
            # Fill diagnostic bytes explicitly, with separate alpha masks.
            scaled = [np.zeros(center.shape, dtype=np.uint8) for _ in range(5)]
            if max_z > min_z:
                scaled[0][elev_valid] = np.floor(np.clip(
                    (center[elev_valid]-min_z)/(max_z-min_z), 0, 1)*255).astype(np.uint8)
            scaled[1][valid] = np.floor((np.clip(dx[valid], -1, 1)+1)*127.5).astype(np.uint8)
            scaled[2][valid] = np.floor((np.clip(dy[valid], -1, 1)+1)*127.5).astype(np.uint8)
            scaled[3][valid] = np.floor(np.clip(mag[valid], 0, 1)*254).astype(np.uint8)
            scaled[4][valid] = np.floor(np.clip(degrees[valid]/45, 0, 1)*254).astype(np.uint8)
            arrays = scaled + [elev_valid.astype(np.uint8)*255, valid.astype(np.uint8)*255]
            for band, array in enumerate(arrays, 1):
                previews.GetRasterBand(band).WriteArray(array, 0, row)
        for ds in [angle_ds, mag_ds, valid_ds, costs, previews]:
            ds.FlushCache()
        # PNG is portable imagery; spatial reference lives in YAML/metadata and TIFFs.
        gdal.SetConfigOption('GDAL_PAM_ENABLED', 'NO')
        gdal.Translate(str(work/'occupancy.png'), costs, format='PNG')
        for band, name in enumerate(['heightmap_norm', 'slope_x_norm', 'slope_y_norm',
                                      'slope_length_norm', 'slope'], 1):
            mem = gdal.Translate('', previews, format='MEM', bandList=[band, 6 if band == 1 else 7])
            mem.GetRasterBand(1).SetColorInterpretation(gdal.GCI_GrayIndex)
            mem.GetRasterBand(2).SetColorInterpretation(gdal.GCI_AlphaBand)
            gdal.Translate(str(work/(name+'.png')), mem, format='PNG')
            mem = None
        anchor = config['anchor']
        anchor_transform = osr.CoordinateTransformation(crs(anchor['crs']), target)
        ax, ay, _ = anchor_transform.TransformPoint(anchor['longitude'], anchor['latitude'], 0)
        geo = target.CloneGeogCS()
        geo.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        inverse = osr.CoordinateTransformation(target, geo)
        corners = {}
        for name, x, y in [('NW', bounds[0], bounds[3]), ('NE', bounds[2], bounds[3]),
                           ('SE', bounds[2], bounds[1]), ('SW', bounds[0], bounds[1])]:
            lon, lat, _ = inverse.TransformPoint(x, y)
            corners[name] = {'projected_m': [x, y], 'local_m': [x-ax, y-ay],
                             'longitude': lon, 'latitude': lat}
        local_origin = [bounds[0]-ax, bounds[1]-ay, 0.0]
        yaml = (f'image: occupancy.png\nresolution: {res!r}\norigin: {local_origin!r}\n'
                'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\nmode: raw\n')
        (work/'map.yaml').write_text(yaml)
        metadata = {
            'size': [width, height], 'resolution_m': res, 'geotransform': gt,
            'projected_crs_wkt': projection, 'geographic_crs_wkt': geo.ExportToWkt(),
            'anchor': dict(anchor, projected_m=[ax, ay]),
            'local_frame': 'projected grid coordinates minus anchor; no rotation',
            'navigation_frame_alignment': 'not field-validated; requires matching projection, anchor and yaw',
            'vertical_datum': config['source_vertical_datum'], 'vertical_conversion': False,
            'elevation_range_m': [min_z, max_z], 'valid_elevation_pixels': valid_elevations,
            'valid_slope_pixels': int(histogram[:101].sum()),
            'unknown_cost_pixels': int(histogram[255]), 'occupancy_histogram': histogram.tolist(),
            'corners_outer_edges': corners, 'yaml_origin_lower_left': local_origin,
            'row_order': 'TIFF/PNG north to south; Nav2 loader flips to south to north',
            'cost_encoding': 'raw: 0..100 slope cost; 255 unknown',
            'full_cost_slope_deg': config['full_cost_slope_deg'],
            'hole_filling': False, 'slope_validity': 'all 3x3 DEM samples required, including edges',
        }
        (work/'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
        (work/'config.json').write_text(json.dumps(config, indent=2)+'\n')
        shutil.copyfile(__file__, work/'pipeline_source.py')
        for ds in [dem, angle_ds, mag_ds, valid_ds, costs, previews]:
            ds.FlushCache()
        dem = angle_ds = mag_ds = valid_ds = costs = previews = src = ds = None
        manifest = {
            'status': 'complete', 'input': input_info,
            'source_horizontal_crs_wkt': horizontal.ExportToWkt(),
            'source_original_crs_wkt': gdal.Open(str(source)).GetProjection(),
            'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                         'gdal': gdal.VersionInfo('--version'),
                         'proj': f'{osr.GetPROJVersionMajor()}.{osr.GetPROJVersionMinor()}.{osr.GetPROJVersionMicro()}'},
            'script_sha256': digest(__file__), 'config_sha256': digest(config_path),
            'proj_network': False,
            'warp': dict(warp_opts, outputBounds=bounds),
            'outputs': {p.name: digest(p) for p in sorted(work.iterdir()) if p.is_file()},
        }
        (work/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        work.rename(output)
    print(f'Created {output}: {width}x{height}, {res} m/cell; '
          f'{metadata["unknown_cost_pixels"]} unknown cost cells')
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path(__file__).parent/'config/mdrs-east.json')
    p.add_argument('--output', type=Path, required=True, help='New directory; existing outputs are never overwritten')
    args = p.parse_args()
    try:
        build(args.config, args.output)
    except (ValueError, RuntimeError, KeyError) as e:
        p.exit(1, f'Pipeline failed: {e}\n')


if __name__ == '__main__':
    main()
