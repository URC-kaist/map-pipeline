#!/usr/bin/python3
"""Package a centered, metric DEM crop as an offline Gazebo Fortress world."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

os.environ['PROJ_NETWORK'] = 'OFF'
import numpy as np
from osgeo import gdal, osr
from export_mesh import export
from pipeline import digest, NODATA


def element(parent, tag, text=None, **attrib):
    node = ET.SubElement(parent, tag, attrib)
    if text is not None:
        node.text = str(text)
    return node


def write_xml(path, root):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='unicode', xml_declaration=True)


def model_xml(prefix=''):
    model = ET.Element('model', name='dem_terrain')
    element(model, 'static', 'true')
    link = element(model, 'link', name='terrain_link')
    for kind, filename in [('collision', 'terrain.stl'), ('visual', 'terrain.obj')]:
        node = element(link, kind, name=f'terrain_{kind}')
        mesh = element(element(node, 'geometry'), 'mesh')
        element(mesh, 'uri', prefix + filename)
        element(mesh, 'scale', '1 1 1')
    return model


def world_xml(width, height, zcenter, zmax, peak, reference, view='detail'):
    root = ET.Element('sdf', version='1.8')
    world = element(root, 'world', name='map_preview')
    physics = element(world, 'physics', name='default', type='ignored')
    element(physics, 'max_step_size', '.001')
    element(physics, 'real_time_factor', '1')
    for short, name in [('physics', 'Physics'), ('user-commands', 'UserCommands'),
                        ('scene-broadcaster', 'SceneBroadcaster'), ('sensors', 'Sensors')]:
        plugin = element(world, 'plugin', filename=f'ignition-gazebo-{short}-system',
                         name=f'ignition::gazebo::systems::{name}')
        if short == 'sensors':
            element(plugin, 'render_engine', 'ogre2')
    scene = element(world, 'scene')
    element(scene, 'ambient', '.3 .3 .3 1')
    element(scene, 'background', '.12 .17 .21 1')
    element(scene, 'grid', 'false')
    light = element(world, 'light', name='sun', type='directional')
    element(light, 'cast_shadows', 'true')
    element(light, 'diffuse', '.95 .95 .95 1')
    element(light, 'specular', '.1 .1 .1 1')
    element(light, 'direction', '.8 -.4 -.45')
    attenuation = element(light, 'attenuation')
    element(attenuation, 'range', '2000')
    element(attenuation, 'constant', '1')
    # Both world and standalone model are relocatable; no file:// absolute paths.
    world.append(model_xml('model/'))
    # Presentation-only metric axes: no collision, no terrain or physics changes.
    axes = element(world, 'model', name='presentation_axes')
    element(axes, 'static', 'true')
    element(axes, 'pose', ' '.join(str(v) for v in [*reference, 0, 0, 0]))
    axis_link = element(axes, 'link', name='axes_link')
    for name, size, pose, color in [
        ('x', '20 .5 .5', '10 0 0 0 0 0', '1 .15 .12 1'),
        ('y', '.5 20 .5', '0 10 0 0 0 0', '.15 .85 .25 1'),
        ('z', '.5 .5 20', '0 0 10 0 0 0', '.15 .4 1 1')]:
        visual = element(axis_link, 'visual', name=name)
        element(visual, 'pose', pose)
        element(element(element(visual, 'geometry'), 'box'), 'size', size)
        material = element(visual, 'material')
        for component in ['ambient', 'diffuse', 'emissive']:
            element(material, component, color)
    distance = max(width, height)
    if view == 'detail':
        target_x, target_y, target_z = peak[0], peak[1], .65*zmax
        camera_x, camera_y = target_x-.55*width, target_y-.5*height
        camera_z = target_z+.23*distance
    else:
        target_x, target_y, target_z = 0, 0, zcenter
        camera_x, camera_y = -.68*distance, -.82*distance
        camera_z = zmax+.8*distance
    yaw = math.atan2(target_y-camera_y, target_x-camera_x)
    pitch = math.atan2(camera_z-target_z, math.hypot(target_x-camera_x, target_y-camera_y))
    pose = f'{camera_x} {camera_y} {camera_z} 0 {pitch} {yaw}'
    gui = element(world, 'gui', fullscreen='0')
    view = element(gui, 'plugin', filename='MinimalScene', name='3D View')
    element(view, 'engine', 'ogre2')
    element(view, 'scene', 'scene')
    element(view, 'camera_pose', pose)
    for filename in ['GzSceneManager', 'InteractiveViewControl', 'CameraTracking']:
        element(gui, 'plugin', filename=filename, name=filename)
    camera_model = element(world, 'model', name='overview_camera')
    element(camera_model, 'static', 'true')
    element(camera_model, 'pose', pose)
    sensor = element(element(camera_model, 'link', name='camera_link'),
                     'sensor', name='overview', type='camera')
    element(sensor, 'always_on', 'true')
    element(sensor, 'update_rate', '1')
    element(sensor, 'topic', '/map_pipeline/overview')
    camera = element(sensor, 'camera')
    element(camera, 'horizontal_fov', '.95' if view == 'detail' else '1.2')
    image = element(camera, 'image')
    element(image, 'width', '960')
    element(image, 'height', '720')
    element(image, 'format', 'R8G8B8')
    clip = element(camera, 'clip')
    element(clip, 'near', '.1')
    element(clip, 'far', max(2000, distance*10))
    return root


def package(result, output, textures, area_fraction=.01, stride=8, view='detail'):
    result, output = Path(result).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new output directory')
    if not math.isfinite(area_fraction) or not 0 < area_fraction <= 1:
        raise ValueError('area_fraction must be in (0, 1]')
    if stride < 1 or not textures:
        raise ValueError('Positive stride and georeferenced RGB texture(s) required')
    if view not in ('detail', 'overview'):
        raise ValueError('view must be detail or overview')
    ds = gdal.Open(str(result/'dem.tif'))
    gt = ds.GetGeoTransform()
    if gt[2] != 0 or gt[4] != 0 or gt[1] <= 0 or gt[5] >= 0:
        raise ValueError('Requires a north-up projected DEM')
    if not ds.GetSpatialRef().IsProjected() or abs(ds.GetSpatialRef().GetLinearUnits()-1) > 1e-9:
        raise ValueError('Requires projected metre coordinates')
    full_meta = json.loads((result/'metadata.json').read_text())
    full_gt = tuple(full_meta['geotransform'])
    if full_gt != gt or full_meta['size'] != [ds.RasterXSize, ds.RasterYSize]:
        raise ValueError('DEM and metadata grid mismatch')
    if not ds.GetSpatialRef().IsSame(osr.SpatialReference(full_meta['projected_crs_wkt'])):
        raise ValueError('DEM and metadata projection mismatch')
    width = max(2, round(ds.RasterXSize*math.sqrt(area_fraction)))
    height = max(2, round(ds.RasterYSize*math.sqrt(area_fraction)))
    if width > ds.RasterXSize or height > ds.RasterYSize:
        raise ValueError('Source too small for a mesh crop')
    xoff, yoff = (ds.RasterXSize-width)//2, (ds.RasterYSize-height)//2
    left, top = gt[0]+xoff*gt[1], gt[3]+yoff*gt[5]
    right, bottom = left+width*gt[1], top+height*gt[5]
    cx, cy = (left+right)/2, (bottom+top)/2
    z = ds.ReadAsArray(xoff, yoff, width, height)
    nodata = ds.GetRasterBand(1).GetNoDataValue()
    valid = np.isfinite(z) & (z != NODATA)
    if nodata is not None:
        valid &= z != nodata
    if not valid.all():
        raise ValueError('Gazebo crop contains unknown terrain; choose a fully valid crop')
    texture_sources = []
    for path in textures:
        rgb = gdal.Open(str(path))
        if (rgb.RasterCount != 3 or rgb.GetSpatialRef() is None or
                any(rgb.GetRasterBand(i).DataType != gdal.GDT_Byte for i in range(1, 4))):
            raise ValueError('Texture inputs must be georeferenced 8-bit three-band RGB TIFFs')
        texture_sources.append({'file': Path(path).name, 'sha256': digest(path)})
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.gazebo-', dir=output.parent) as tmp:
        work = Path(tmp)
        crop = work/'crop'
        crop.mkdir()
        gdal.Translate(str(crop/'dem.tif'), ds, srcWin=[xoff, yoff, width, height])
        cropped_meta = copy.deepcopy(full_meta)
        cropped_meta['size'] = [width, height]
        cropped_meta['geotransform'] = [left, gt[1], 0, top, 0, gt[5]]
        cropped_meta['anchor'] = {'projected_m': [cx, cy]}
        cropped_meta['local_frame'] = 'projected grid minus crop center; metres; no rotation'
        (crop/'metadata.json').write_text(json.dumps(cropped_meta))
        # Warp each original georeferenced source, in supplied order (last valid wins).
        rgba = gdal.Warp('', [str(p) for p in textures], format='MEM',
                         dstSRS=ds.GetProjection(), outputBounds=[left, bottom, right, top],
                         width=width, height=height, resampleAlg='bilinear', dstAlpha=True,
                         errorThreshold=0)
        if rgba.RasterCount != 4 or not (rgba.GetRasterBand(4).ReadAsArray() == 255).all():
            raise ValueError('RGB sources do not fully cover the crop')
        texture = work/'rgb.tif'
        gdal.Translate(str(texture), rgba, bandList=[1, 2, 3])
        package_dir = work/'package'
        package_dir.mkdir()
        mesh = export(crop, package_dir/'model', stride, texture, 'both')
        # Replace temporary paths with durable source identities before publication.
        mesh['texture']['input'] = 'georeferenced RGB crop from recorded source TIFFs'
        (package_dir/'model/mesh.json').write_text(json.dumps(mesh, indent=2)+'\n')
        model_sdf = ET.Element('sdf', version='1.8')
        model_sdf.append(model_xml())
        write_xml(package_dir/'model/model.sdf', model_sdf)
        config = ET.Element('model')
        element(config, 'name', 'DEM terrain')
        element(config, 'version', '1.0')
        element(config, 'sdf', 'model.sdf', version='1.8')
        element(config, 'description', 'Cropped DEM terrain with local georeferenced NAIP texture')
        write_xml(package_dir/'model/model.config', config)
        z0 = mesh['z_offset_m']
        pr, pc = np.unravel_index(z.argmax(), z.shape)
        peak = [(pc+.5)*gt[1]-(right-left)/2,
                (pr+.5)*gt[5]+(top-bottom)/2, float(z[pr, pc])-z0]
        ar, ac = min(pr+160, height-1), max(pc-140, 0)
        # Float the visual-only reference above all terrain spanned by its arms.
        steps_x = max(1, math.ceil(20/gt[1]))
        steps_y = max(1, math.ceil(20/-gt[5]))
        reference_height = max(z[ar, ac:min(ac+steps_x+1, width)].max(),
                               z[max(0, ar-steps_y):ar+1, ac].max())
        reference = [(ac+.5)*gt[1]-(right-left)/2,
                     (ar+.5)*gt[5]+(top-bottom)/2, float(reference_height)-z0+2]
        world = world_xml(right-left, top-bottom, float(z[height//2, width//2])-z0,
                          float(z.max())-z0, peak, reference, view)
        write_xml(package_dir/'world.sdf', world)
        # Store crop inputs for transparent regeneration and cross-checking.
        gdal.Translate(str(package_dir/'dem.tif'), str(crop/'dem.tif'))
        record = {
            'source_dem_sha256': digest(result/'dem.tif'),
            'source_metadata_sha256': digest(result/'metadata.json'),
            'export_script_sha256': digest(__file__),
            'texture_sources': texture_sources,
            'requested_area_fraction': area_fraction,
            'actual_area_fraction': width*height/(ds.RasterXSize*ds.RasterYSize),
            'crop_pixel_window': [xoff, yoff, width, height],
            'crop_bounds_projected_m': [left, bottom, right, top],
            'crop_size_m': [right-left, top-bottom],
            'projected_crs_wkt': ds.GetProjection(),
            'world_to_projected': {'easting_offset_m': cx, 'northing_offset_m': cy,
                                   'elevation_offset_m': z0, 'rotation_rad': 0, 'scale': 1},
            'world_to_navigation_xy_offset_m': [cx-full_meta['anchor']['projected_m'][0],
                                               cy-full_meta['anchor']['projected_m'][1]],
            'mesh': {'stride_pixels': stride, 'spacing_m': [stride*gt[1], -stride*gt[5]],
                     'triangles': mesh['triangles'], 'vertices': mesh['vertices']},
            'presentation': {'view': view, 'peak_world_m': peak,
                             'axes_origin_world_m': reference, 'axes_length_m': 20,
                             'axes_role': 'visual-only XYZ metric reference; no collisions',
                             'camera_pose': [float(v) for v in world.find('.//model[@name="overview_camera"]/pose').text.split()],
                             'horizontal_fov_rad': float(world.find('.//sensor/camera/horizontal_fov').text)},
            'limits': 'Grid-aligned cropped simulation frame, not ENU or established live Nav2 TF; '
                      'vertical datum unchanged; sampled surface; no vertical exaggeration; '
                      'not a validated rover dynamics model',
            'outputs': {p.relative_to(package_dir).as_posix(): digest(p)
                        for p in sorted(package_dir.rglob('*')) if p.is_file()},
        }
        (package_dir/'gazebo.json').write_text(json.dumps(record, indent=2)+'\n')
        package_dir.rename(output)
    print(f'Created {output}: {right-left:g} × {top-bottom:g} m; {mesh["triangles"]} triangles')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('result', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--texture', required=True, type=Path, nargs='+')
    p.add_argument('--area-fraction', type=float, default=.01)
    p.add_argument('--stride', type=int, default=8)
    p.add_argument('--view', choices=['detail', 'overview'], default='detail')
    args = p.parse_args()
    try:
        package(args.result, args.output, args.texture, args.area_fraction, args.stride, args.view)
    except (ValueError, RuntimeError) as e:
        p.exit(1, f'Gazebo export failed: {e}\n')
