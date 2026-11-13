#!/usr/bin/python3
"""Optional native roundtrip using installed ROS Humble Nav2 (without ROS launch)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path, help='Pipeline result directory containing map.yaml')
p.add_argument('--report', type=Path)
p.add_argument('--ros-prefix', type=Path, default=Path('/opt/ros/humble'))
args = p.parse_args()
root = Path(__file__).resolve().parent
output = args.output.resolve()
ros = args.ros_prefix
with tempfile.TemporaryDirectory(prefix='map-nav2-check-') as tmp:
    tmp = Path(tmp)
    env = dict(os.environ, LD_LIBRARY_PATH=str(ros/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''))
    command = ['g++', '-std=c++17', str(root/'check_nav2.cpp'), '-o', str(tmp/'check'),
               '-L'+str(ros/'lib'), '-lmap_io', '-I'+str(ros/'include')]
    command += ['-I'+str(ros/'include'/name) for name in
                ['nav_msgs','geometry_msgs','std_msgs','builtin_interfaces',
                 'rosidl_runtime_cpp','rosidl_runtime_c','rosidl_typesupport_interface']]
    compilation = subprocess.run(command, env=env, capture_output=True, text=True)
    if compilation.returncode:
        p.exit(1, compilation.stderr)
    result = subprocess.run([str(tmp/'check'), str(output/'map.yaml'), str(tmp/'grid.bin')],
                            env=env, check=True, capture_output=True, text=True)
    image = np.asarray(Image.open(output/'occupancy.png'))
    raw = np.fromfile(tmp/'grid.bin', dtype=np.int8).reshape(image.shape)
    expected = np.flipud(image).astype(np.int16)
    expected[expected == 255] = -1
    np.testing.assert_array_equal(raw, expected)
    report = {'native_loader': str(ros/'lib/libmap_io.so'),
              'result': 'every decoded cell equals the expected vertically flipped raw cost',
              'cells_compared': int(image.size), 'unknown_cells': int((raw == -1).sum()),
              'loader_log': result.stdout+result.stderr}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'loader_log'}, indent=2))
