#!/usr/bin/python3
"""Optional real Gazebo Fortress collision smoke check (no renderer / rover)."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
from export_gazebo import element, write_xml
from pipeline import digest


def ground_at(triangles, x, y):
    xy = triangles[:, :, :2]
    candidate = ((xy.min(axis=1) <= [x, y]).all(axis=1) &
                 (xy.max(axis=1) >= [x, y]).all(axis=1))
    for triangle in triangles[candidate]:
        a, b, c = triangle
        uv = np.linalg.solve(np.stack([b[:2]-a[:2], c[:2]-a[:2]], axis=1),
                             np.array([x, y])-a[:2])
        if (uv >= -1e-7).all() and uv.sum() <= 1+1e-7:
            return float(a[2]+uv[0]*(b[2]-a[2])+uv[1]*(c[2]-a[2]))
    raise ValueError('Probe left the mesh surface')


def verify(package, output):
    package, output = Path(package).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new verification directory')
    record = json.loads((package/'gazebo.json').read_text())
    for name, expected in record['outputs'].items():
        if digest(package/name) != expected:
            raise ValueError(f'Package manifest mismatch: {name}')
    vertices, faces = [], []
    for line in (package/'model/terrain.obj').read_text().splitlines():
        if line.startswith('v '):
            vertices.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):
            faces.append([int(i.split('/')[0])-1 for i in line.split()[1:]])
    triangles = np.asarray(vertices)[np.asarray(faces)]
    center = triangles.mean(axis=1)
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    flatness = normals[:, 2]/np.linalg.norm(normals, axis=1)
    central = np.linalg.norm(center[:, :2], axis=1) < min(record['crop_size_m'])/8
    if not central.any():
        raise ValueError('No central test triangle')
    index = np.flatnonzero(central)[np.argmax(flatness[central])]
    x, y, z = center[index]
    tree = ET.parse(package/'world.sdf')
    world = tree.find('world')
    for plugin in list(world.findall('plugin')):
        if plugin.attrib.get('name', '').endswith('::Sensors'):
            world.remove(plugin)
    for model in list(world.findall('model')):
        if model.attrib['name'] == 'overview_camera':
            world.remove(model)
    for uri in tree.findall('.//mesh/uri'):
        uri.text = (package/uri.text).as_uri()
    model = element(world, 'model', name='collision_probe')
    element(model, 'pose', f'{x} {y} {z+2.5} 0 0 0')
    link = element(model, 'link', name='probe_link')
    inertial = element(link, 'inertial')
    element(inertial, 'mass', 1)
    inertia = element(inertial, 'inertia')
    for axis in ['ixx', 'iyy', 'izz']:
        element(inertia, axis, '.025')
    collision = element(link, 'collision', name='probe_collision')
    sphere = element(element(collision, 'geometry'), 'sphere')
    element(sphere, 'radius', '.25')
    output.mkdir(parents=True)
    write_xml(output/'probe.sdf', tree.getroot())
    env = dict(os.environ, IGN_PARTITION=f'map-collision-{os.getpid()}',
               IGN_GAZEBO_RESOURCE_PATH=str(package))
    command = ['ign', 'gazebo', '-s', '-r', '--iterations', '6000', '-z', '1000',
               str(output/'probe.sdf')]
    with open(output/'poses.jsonl', 'w') as poses, open(output/'gazebo.log', 'w') as log:
        listener = subprocess.Popen(['ign', 'topic', '-e', '--json-output', '-t',
                                     '/world/map_preview/dynamic_pose/info'],
                                    stdout=poses, stderr=log, env=env, start_new_session=True)
        server = None
        try:
            server = subprocess.Popen(command, stdout=log, stderr=log, env=env, start_new_session=True)
            code = server.wait(timeout=45)
        finally:
            for process in [server, listener]:
                if process is not None and process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
    decoder, data, positions = json.JSONDecoder(), (output/'poses.jsonl').read_text(), []
    while data.strip():
        obj, end = decoder.raw_decode(data.lstrip())
        data = data.lstrip()[end:]
        for pose in obj.get('pose', []):
            if pose.get('name') == 'collision_probe':
                positions.append([float(pose['position'].get(axis, 0)) for axis in 'xyz'])
    if code or len(positions) < 5:
        raise ValueError(f'Simulator exited {code}; only {len(positions)} probe poses')
    final = positions[-1]
    ground = ground_at(triangles, *final[:2])
    clearance = final[2]-ground
    if not .15 < clearance < .4 or max(p[2] for p in positions)-final[2] < 1:
        raise ValueError(f'Probe did not settle on the surface: clearance={clearance}')
    report = {'package_manifest_sha256': digest(package/'gazebo.json'),
              'verification_script_sha256': digest(__file__),
              'iterations': 6000, 'pose_samples': len(positions), 'exit_code': code,
              'initial_position_m': [float(x), float(y), float(z+2.5)],
              'final_position_m': final, 'mesh_height_at_final_xy_m': ground,
              'sphere_radius_m': .25, 'final_clearance_m': clearance,
              'scope': 'One falling sphere supported by the exported STL in Gazebo/DART; '
                       'not a complete mesh collision survey or rover dynamics validation'}
    (output/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    verify(args.package, args.output)
