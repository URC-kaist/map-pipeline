#!/usr/bin/python3
"""Export small, real-output README illustrations; no browser/Node dependency.

Run from the repository root. Requires GDAL, NumPy, Pillow and DejaVu fonts.
The output directory must not already exist. Original outputs are read only.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

os.environ['PROJ_NETWORK'] = 'OFF'
import numpy as np
from osgeo import gdal, osr
from PIL import Image, ImageDraw, ImageFont

gdal.UseExceptions()
BG = '#f3f5f7'
INK = '#172c3a'
MUTED = '#4c606c'
UNKNOWN = (204, 52, 164)
W, H = 320, 440
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def text(draw, xy, value, size=14, fill=INK, bold=False):
    font = ImageFont.truetype(FONT + ('-Bold' if bold else '') + '.ttf', size)
    draw.text(xy, value, font=font, fill=fill)


def palette(values, low, high, stops, valid):
    t = np.clip((values-low)/(high-low), 0, 1)
    t = np.nan_to_num(t)
    colors = np.asarray(stops)
    positions = np.linspace(0, 1, len(colors))
    out = np.stack([np.interp(t, positions, colors[:, i]) for i in range(3)], -1)
    out[~valid] = UNKNOWN
    return Image.fromarray(out.astype('uint8'))


def srs(code):
    result = osr.SpatialReference()
    result.SetFromUserInput(code)
    result.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return result


def camera_pixel(point, pose, fov, size):
    """Project world coordinates through the SDF pinhole camera (+X forward)."""
    _, _, _, roll, pitch, yaw = pose
    if abs(roll) > 1e-10:
        raise ValueError('Preview annotation expects an unrolled camera')
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    rotation = np.array([[cy*cp, -sy, cy*sp], [sy*cp, cy, sy*sp], [-sp, 0, cp]])
    forward, left, up = rotation.T @ (np.asarray(point)-pose[:3])
    if forward <= 0:
        raise ValueError('Reference lies behind the camera')
    focal = size[0]/(2*math.tan(fov/2))
    return np.array([size[0]/2-left*focal/forward, size[1]/2-up*focal/forward])


def sample_tiles(root, bounds, zoom):
    """Nearest sample actual XYZ PNGs on the common EPSG:6341 preview grid."""
    west, south, east, north = bounds
    xx, yy = np.meshgrid(west+(np.arange(W)+.5)*(east-west)/W,
                         north-(np.arange(H)+.5)*(north-south)/H)
    transform = osr.CoordinateTransformation(srs('EPSG:6341'), srs('EPSG:3857'))
    points = np.asarray(transform.TransformPoints(np.stack([xx.ravel(), yy.ravel()], -1)))
    half = math.pi * 6378137
    px = np.floor((points[:, 0]+half)/(2*half)*256*2**zoom).astype(int)
    py = np.floor((half-points[:, 1])/(2*half)*256*2**zoom).astype(int)
    keys = np.stack([px//256, py//256], -1)
    result = np.zeros((W*H, 3), dtype='uint8')
    used = {}
    for tx, ty in np.unique(keys, axis=0):
        path = root / str(zoom) / str(tx) / f'{ty}.png'
        with Image.open(path) as image:
            tile = np.asarray(image.convert('RGBA'))
        mask = (keys[:, 0] == tx) & (keys[:, 1] == ty)
        samples = tile[py[mask] % 256, px[mask] % 256]
        result[mask] = np.where(samples[:, 3:4] > 0, samples[:, :3], UNKNOWN)
        used[path.relative_to(root).as_posix()] = sha(path)
    return Image.fromarray(result.reshape(H, W, 3)), used


def card(image, title, subtitle, legend, stops=None, limits=None, note=''):
    page = Image.new('RGB', (368, 630), 'white')
    draw = ImageDraw.Draw(page)
    text(draw, (24, 18), title, 20, bold=True)
    text(draw, (24, 48), subtitle, 12, MUTED)
    page.paste(image, (24, 78))
    # Grid north and a 1 km bar: common 4 km wide projected footprint.
    draw.rectangle((32, 86, 102, 113), fill=INK)
    text(draw, (38, 90), 'Grid N ↑', 12, 'white')
    draw.rectangle((32, 480, 130, 510), fill=INK)
    draw.line((40, 499, 120, 499), fill='white', width=3)
    text(draw, (40, 482), '1 km', 11, 'white')
    text(draw, (24, 532), legend, 13, bold=True)
    if stops:
        gradient = np.broadcast_to(np.linspace(0, 1, W), (12, W))
        bar = palette(gradient, 0, 1, stops, np.ones(gradient.shape, bool))
        page.paste(bar, (24, 554))
        text(draw, (24, 570), limits[0], 12, MUTED)
        text(draw, (268, 570), limits[1], 12, MUTED)
    else:
        text(draw, (24, 554), 'NAIP 2024 · original detail 60 cm', 12, MUTED)
        text(draw, (24, 574), 'Physical XYZ zooms 14–18', 12, MUTED)
    text(draw, (24, 604), note, 11, MUTED)
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terrain', type=Path, default=Path('Lidar-pipeline/output/mdrs-expanded'))
    parser.add_argument('--rgb', type=Path, default=Path('RGB-pipeline/output/mdrs-expanded'))
    parser.add_argument('--output', type=Path, default=Path('docs/images'))
    parser.add_argument('--gazebo', type=Path, default=Path('Lidar-pipeline/output/mdrs-gazebo-relief'))
    parser.add_argument('--capture', type=Path, default=Path('Lidar-pipeline/output/mdrs-gazebo-relief-capture'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new directory')
    region = json.loads(Path('map-region.json').read_text())
    bounds = region['bounds']
    if bounds != [518000, 4248000, 522000, 4253500]:
        parser.error('This layout is for the documented 4 × 5.5 km expanded profile')
    manifest = json.loads((args.terrain/'manifest.json').read_text())
    rgb_manifest = json.loads((args.rgb/'manifest.json').read_text())
    if rgb_manifest['crop_outer_bounds'] != bounds:
        parser.error('RGB and terrain footprints differ')
    files = ['dem.tif', 'occupancy.png']
    fingerprints = {name: sha(args.terrain/name) for name in files}
    for name, digest in fingerprints.items():
        if digest != manifest['outputs'][name]:
            raise ValueError(f'Output no longer matches terrain manifest: {name}')
    arrays = {}
    for name in files:
        ds = gdal.Open(str(args.terrain/name))
        if (ds.RasterXSize, ds.RasterYSize) != (8000, 11000):
            raise ValueError(f'Unexpected source dimensions: {name}')
        # Raw Nav2 PNG is georeferenced by its paired YAML/metadata, not PNG tags.
        if name == 'dem.tif':
            gt = ds.GetGeoTransform()
            if gt != (518000, .5, 0, 4253500, 0, -.5):
                raise ValueError(f'Unexpected geotransform: {name}')
        band = ds.GetRasterBand(1)
        arrays[name] = band.ReadAsArray(buf_xsize=W, buf_ysize=H,
                                       resample_alg=gdal.GRIORA_NearestNeighbour)
    elevation = arrays['dem.tif']
    cost = arrays['occupancy.png']
    if not ((cost <= 100) | (cost == 255)).all():
        raise ValueError('Unexpected Nav2 raw cost encoding')
    valid = np.isfinite(elevation) & (elevation != -9999)
    low = math.floor(float(elevation[valid].min())/10)*10
    high = math.ceil(float(elevation[valid].max())/10)*10
    terrain_colors = [(34, 92, 85), (143, 164, 101), (208, 178, 124), (246, 240, 221)]
    heat = [(246, 242, 214), (241, 180, 82), (206, 74, 51), (80, 34, 51)]
    rgb, used = sample_tiles(args.rgb/'site/tiles/naip', bounds, 16)
    gazebo = json.loads((args.gazebo/'gazebo.json').read_text())
    if gazebo['crop_size_m'] != [400, 550] or gazebo['mesh']['spacing_m'] != [4, 4]:
        raise ValueError('This preview layout describes the default 400 × 550 m / 4 m Gazebo profile')
    capture = json.loads((args.capture/'capture.json').read_text())
    if capture['package_manifest_sha256'] != sha(args.gazebo/'gazebo.json'):
        raise ValueError('Camera capture belongs to a different Gazebo package')
    if gazebo['source_dem_sha256'] != fingerprints['dem.tif']:
        raise ValueError('Gazebo terrain belongs to a different DEM')
    frame_name = sorted(capture['frames'])[-1]
    frame_path = args.capture/'frames'/frame_name
    if sha(frame_path) != capture['frames'][frame_name]:
        raise ValueError('Camera frame hash mismatch')
    with Image.open(frame_path) as frame:
        frame = frame.convert('RGB')
    three_d = Image.new('RGB', (368, 630), 'white')
    td = ImageDraw.Draw(three_d)
    text(td, (24, 18), '03  Gazebo terrain', 20, bold=True)
    text(td, (24, 48), 'Actual simulator camera · RGB texture', 12, MUTED)
    three_d.paste(Image.new('RGB', (W, H), frame.getpixel((0, 0))), (24, 78))
    # Portrait detail for the poster; keep the full camera field of view separately.
    presentation = gazebo['presentation']
    peak_pixel = camera_pixel(presentation['peak_world_m'], presentation['camera_pose'],
                              presentation['horizontal_fov_rad'], frame.size)
    crop_h = round(frame.height*.72)
    crop_w = round(crop_h*W/H)
    left_px = round(np.clip(peak_pixel[0]-crop_w/2, 0, frame.width-crop_w))
    presentation_crop = [left_px, frame.height-crop_h, left_px+crop_w, frame.height]
    thumb = frame.crop(presentation_crop)
    thumb.thumbnail((W, H))
    thumb_origin = np.array([24+(W-thumb.width)//2, 78+(H-thumb.height)//2])
    three_d.paste(thumb, tuple(thumb_origin))
    for axis, color in zip(range(3), ['#ff7560', '#6bff84', '#71baff']):
        endpoint = np.array(presentation['axes_origin_world_m'])
        endpoint[axis] += presentation['axes_length_m']
        pixel = camera_pixel(endpoint, presentation['camera_pose'],
                             presentation['horizontal_fov_rad'], frame.size)
        xy = thumb_origin+(pixel-np.array(presentation_crop[:2])) * np.array(
            [thumb.width/crop_w, thumb.height/crop_h])
        if 24 <= xy[0] < 344 and 78 <= xy[1] < 518:
            td.text(tuple(xy+[3, -8]), 'XYZ'[axis], fill=color,
                    font=ImageFont.truetype(FONT+'-Bold.ttf', 13), stroke_width=2, stroke_fill=INK)
    text(td, (24, 532), 'Centered crop · 400 × 550 m', 13, bold=True)
    text(td, (24, 554), 'Low oblique camera · detail crop', 12, MUTED)
    text(td, (24, 574), 'XYZ reference: 20 m per arm', 12, MUTED)
    text(td, (24, 604), '4 m sampled mesh · true metre scale', 11, MUTED)
    # Mark the smaller simulation footprint on all three full-footprint panels.
    left, bottom, right, top = gazebo['crop_bounds_projected_m']
    box = ((left-bounds[0])/(bounds[2]-bounds[0])*W,
           (bounds[3]-top)/(bounds[3]-bounds[1])*H,
           (right-bounds[0])/(bounds[2]-bounds[0])*W,
           (bounds[3]-bottom)/(bounds[3]-bounds[1])*H)
    elevation_image = palette(elevation, low, high, terrain_colors, valid)
    cost_image = palette(cost, 0, 100, heat, cost != 255)
    for image in [elevation_image, cost_image, rgb]:
        ImageDraw.Draw(image).rectangle(box, outline='#153c4e', width=3)
        ImageDraw.Draw(image).rectangle(box, outline='#46ecff', width=1)
    panels = [
        ('elevation', card(elevation_image,
                           '01  Elevation', 'Mosaicked bare-earth DEM',
                           'Provider elevation · metres', terrain_colors,
                           (f'{low} m', f'{high} m'), 'Mixed 0.5 / 1 m sources → 0.5 m grid')),
        ('nav2-costmap', card(cost_image,
                             '02  Nav2 costmap', 'Nav2 raw PNG + map.yaml',
                             'Slope-derived cost · 0–100', heat, ('0', '100'),
                             '255 = unknown · not occupancy probability')),
        ('gazebo-terrain', three_d),
        ('rgb-tiles', card(rgb, '04  Offline RGB tiles', 'Sampled from generated XYZ PNGs',
                          'Natural-colour aerial imagery', note='XYZ z16 → common projected preview grid')),
    ]
    for name, digest in used.items():
        if digest != rgb_manifest['outputs'][f'site/tiles/naip/{name}']:
            raise ValueError(f'Tile no longer matches RGB manifest: {name}')
    poster = Image.new('RGB', (1536, 970), BG)
    d = ImageDraw.Draw(poster)
    text(d, (32, 24), 'MAP PIPELINE', 32, bold=True)
    text(d, (32, 70), 'Real geospatial inputs → terrain products + offline dashboard imagery', 20)
    for box, title, detail in [((32, 112, 1136, 184), 'BARE-EARTH DEMs  →  MOSAIC  →  NAV2 COSTMAP / GAZEBO TERRAIN',
                               'Utah 2018 / 2020 / 2022 DEMs · NAIP RGB for Gazebo texture · EPSG:6341'),
                              ((1152, 112, 1520, 184), 'NAIP RGB → CROP → XYZ',
                               'EPSG:26912 → EPSG:3857')]:
        d.rounded_rectangle(box, radius=10, fill=INK)
        text(d, (box[0]+16, 125), title, 15, 'white', True)
        text(d, (box[0]+16, 154), detail, 12, '#d1e2e8')
    args.output.mkdir(parents=True)
    for i, (name, panel) in enumerate(panels):
        poster.paste(panel, (16+i*384, 204))
        if name in ('rgb-tiles', 'gazebo-terrain'):
            panel.save(args.output/f'{name}.jpg', quality=82, optimize=True)
        else:
            panel.quantize(colors=128).save(args.output/f'{name}.png', optimize=True)
    frame.save(args.output/'gazebo-camera.jpg', quality=82, optimize=True)
    text(d, (32, 881), 'MDRS expanded · 4 × 5.5 km maps · cyan box = smaller Gazebo crop · grid north up on maps', 16, bold=True)
    text(d, (32, 909), 'UGRC / SGID; USDA NAIP · recoloured / resampled previews · magenta = sampled unknown cells', 13, MUTED)
    text(d, (32, 933), 'Overview only: small hazards and the 1-cell unknown border may disappear. Field registration and rover traversability are not established.', 13, MUTED)
    poster.save(args.output/'pipeline-overview.jpg', quality=85, optimize=True)
    record = {
        'profile': 'mdrs-expanded', 'generation_code_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'preview_script_sha256': sha(Path(__file__)),
        'region': region, 'sample_dimensions': [W, H],
        'sampling': 'Nearest cell-centre sampling of full-resolution products; not slope recomputation',
        'nav2_preview': {'source': 'occupancy.png', 'valid_cost_range': [0, 100],
                         'unknown': 255, 'representation': 'Colour-mapped visualization, not a Nav2 input'},
        'elevation_colour_limits_m': [low, high], 'rgb_xyz_zoom': 16,
        'terrain_manifest_sha256': sha(args.terrain/'manifest.json'),
        'terrain_config': json.loads((args.terrain/'config.json').read_text()),
        'terrain_generation_script_sha256': manifest['script_sha256'],
        'terrain_input_sha256': manifest['input']['sha256'],
        'terrain_output_sha256': fingerprints,
        'rgb_manifest_sha256': sha(args.rgb/'manifest.json'),
        'rgb_generation_script_sha256': rgb_manifest['outputs']['generate_source.py'],
        'rgb_config': rgb_manifest['config'],
        'rgb_source_sha256': rgb_manifest['input_sha256'],
        'rgb_sampled_tile_sha256': used,
        'gazebo_package': gazebo,
        'gazebo_capture': capture,
        'gazebo_camera_frame': {'file': frame_name, 'sha256': sha(frame_path)},
        'gazebo_card_presentation_crop_pixels': presentation_crop,
        'assets': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p),
                            'dimensions': list(Image.open(p).size)}
                   for p in sorted(args.output.iterdir())},
        'versions': {'gdal': gdal.VersionInfo('--version'), 'numpy': np.__version__,
                     'pillow': Image.__version__},
    }
    (args.output/'provenance.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record['assets'], indent=2))


if __name__ == '__main__':
    main()
