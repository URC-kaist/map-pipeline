#!/usr/bin/python3
"""Capture an actual Gazebo Fortress camera frame from an exported terrain world.

Requires ign gazebo and a working OGRE2 / OpenGL setup (software Mesa is usable).
No GUI, ROS or Internet is required. Does not change the exported package.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

from pipeline import digest


def capture(package, output, timeout=90):
    package, output = Path(package).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new capture directory')
    record = json.loads((package/'gazebo.json').read_text())
    for name, expected in record['outputs'].items():
        if digest(package/name) != expected:
            raise ValueError(f'Package file no longer matches manifest: {name}')
    tree = ET.parse(package/'world.sdf')
    for uri in tree.findall('.//mesh/uri'):
        uri.text = (package/uri.text).as_uri()
    output.mkdir(parents=True)
    camera = tree.find('.//sensor/camera')
    save = ET.SubElement(camera, 'save', enabled='true')
    ET.SubElement(save, 'path').text = str(output/'frames')
    tree.write(output/'capture.sdf', encoding='unicode')
    command = ['ign', 'gazebo', '-s', '-r', '--iterations', '5000', '-z', '250', '-v', '3',
               str(output/'capture.sdf')]
    env = dict(os.environ, IGN_PARTITION=f'map-pipeline-{os.getpid()}',
               IGN_GAZEBO_RESOURCE_PATH=str(package),
               GZ_SIM_RESOURCE_PATH=str(package))
    start = time.monotonic()
    # Keep the camera active even on versions which suppress unconnected sensors.
    listener = subprocess.Popen(['ign', 'topic', '-e', '-t', '/map_pipeline/overview'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=env, start_new_session=True)
    with open(output/'gazebo.log', 'w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise RuntimeError(f'Gazebo capture timed out; see {output}/gazebo.log')
        finally:
            os.killpg(listener.pid, signal.SIGTERM)
            listener.wait(timeout=5)
    frames = sorted((output/'frames').glob('*.png'))
    if code or not frames:
        raise RuntimeError(f'Gazebo exited {code}, {len(frames)} frames; see {output}/gazebo.log')
    report = {
        'world_sha256': digest(package/'world.sdf'),
        'package_manifest_sha256': digest(package/'gazebo.json'),
        'capture_script_sha256': digest(__file__),
        'engine': 'Gazebo Fortress camera sensor / OGRE2',
        'version': subprocess.check_output(['ign', 'gazebo', '--version'], text=True).strip(),
        'iterations': 5000, 'max_update_rate_hz': 250,
        'elapsed_seconds': round(time.monotonic()-start, 2),
        'exit_code': code,
        'frames': {p.name: digest(p) for p in frames},
        'scope': 'Actual simulator camera render and world load; not rover dynamics validation',
    }
    (output/'capture.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Captured {len(frames)} Gazebo frames in {output}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=90)
    args = p.parse_args()
    try:
        capture(args.package, args.output, args.timeout)
    except (ValueError, RuntimeError, OSError) as e:
        p.exit(1, f'Gazebo capture failed: {e}\n')
