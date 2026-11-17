#!/usr/bin/python3
"""Mosaic the eight downloaded DEMs, preserving their native grid and samples."""
import json
import subprocess
import zipfile
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
root = Path(__file__).resolve().parent
folder = root / 'Lidar'
names = ['12SWH1848', '12SWH1850', '12SWH1852', '12SWH1952',
         '12SWH2048', '12SWH2050', '12SWH2052', '12SWH2152']
for name in names:
    with zipfile.ZipFile(folder / (name + '.zip')) as archive:
        for suffix in ['.tif', '.tfw']:
            if not (folder / (name + suffix)).exists():
                archive.extract(name + suffix, folder)

sources = []
reference = None
coverage = np.zeros((10000, 8000), dtype=np.uint8)
for name in names:
    path = folder / (name + '.tif')
    ds = gdal.Open(str(path))
    crs = ds.GetSpatialRef()
    gt = ds.GetGeoTransform()
    if reference is None:
        reference = crs.Clone()
    assert reference.IsSame(crs), name
    assert gt[1:] == (0.5, 0.0, gt[3], 0.0, -0.5), name
    assert ds.GetRasterBand(1).DataType == gdal.GDT_Float32
    assert ds.GetRasterBand(1).GetNoDataValue() == -9999
    x, y = (gt[0] - 518000) / .5, (4253000 - gt[3]) / .5
    assert x.is_integer() and y.is_integer()
    x, y = int(x), int(y)
    w, h = ds.RasterXSize, ds.RasterYSize
    assert 0 <= x < x+w <= 8000 and 0 <= y < y+h <= 10000
    coverage[y:y+h, x:x+w] += 1
    sources.append({'file': path.name, 'size': [w, h],
                    'geoTransform': gt, 'offset': [x, y],
                    'extent': [gt[0], gt[3] - h*.5, gt[0] + w*.5, gt[3]]})
assert np.all(coverage == 1), 'Source footprints must cover the rectangle exactly once'
del coverage

commands = [
    ['gdalbuildvrt', '-resolution', 'user', '-tr', '0.5', '0.5',
     '-te', '518000', '4248000', '522000', '4253000',
     '-srcnodata', '-9999', '-vrtnodata', '-9999',
     'bare_earth_2018_0p5m.vrt'] + [n + '.tif' for n in names],
    ['gdal_translate', '-of', 'GTiff', '-co', 'TILED=YES', '-co', 'COMPRESS=DEFLATE',
     '-co', 'PREDICTOR=3', '-co', 'BIGTIFF=IF_SAFER',
     'bare_earth_2018_0p5m.vrt', 'bare_earth_2018_0p5m.tif'],
]
for command in commands:
    subprocess.run(command, cwd=folder, check=True)

mosaic = gdal.Open(str(folder / 'bare_earth_2018_0p5m.tif'))
assert mosaic.GetGeoTransform() == (518000., .5, 0., 4253000., 0., -.5)
assert (mosaic.RasterXSize, mosaic.RasterYSize) == (8000, 10000)
assert mosaic.GetSpatialRef().IsSame(reference)
checks = []
for source in sources:
    ds = gdal.Open(str(folder / source['file']))
    w, h = source['size']
    x, y = source['offset']
    nodata = 0
    for row in range(0, h, 256):
        rows = min(256, h-row)
        a = ds.ReadAsArray(0, row, w, rows)
        b = mosaic.ReadAsArray(x, y+row, w, rows)
        assert np.array_equal(a, b, equal_nan=True), source['file']
        nodata += int(np.count_nonzero(a == -9999))
    checks.append({'file': source['file'], 'all_samples_equal': True,
                   'nodata_pixels': nodata})

geographic = reference.CloneGeogCS()
reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
transform = osr.CoordinateTransformation(reference, geographic)
corners = {}
for name, (e, n) in {'NW': (518000, 4253000), 'NE': (522000, 4253000),
                     'SE': (522000, 4248000), 'SW': (518000, 4248000)}.items():
    lon, lat, _ = transform.TransformPoint(e, n)
    corners[name] = {'easting_m': e, 'northing_m': n,
                     'longitude_NAD83_2011': lon, 'latitude_NAD83_2011': lat}
report = {'gdal_version': gdal.VersionInfo('--version'), 'sources': sources,
          'crs': 'EPSG:6341', 'geographic_crs': 'EPSG:6318',
          'size': [8000, 10000], 'resolution_m': .5,
          'corners_outer_edges': corners, 'commands': commands,
          'footprints_cover_rectangle_once': True, 'sample_checks': checks,
          'nodata_pixels': sum(c['nodata_pixels'] for c in checks),
          'vertical_datum': 'Not established from inspected TIFF metadata'}
(folder / 'mosaic-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
