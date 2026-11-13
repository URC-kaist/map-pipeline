#!/usr/bin/python3
"""Optional MapLibre demo: decorate an existing tile result with local assets."""
import argparse
import json
from pathlib import Path
import shutil
from generate import sha


def build_viewer(result,assets):
    result=Path(result).resolve();assets=Path(assets).resolve()
    names={'dist/maplibre-gl.js':'maplibre-gl.js','dist/maplibre-gl.css':'maplibre-gl.css','LICENSE.txt':'LICENSE.txt'}
    for f in ['package.json',*names]:
        if not (assets/f).is_file():raise ValueError(f'Missing optional viewer asset: {assets/f}')
    metadata=json.loads((result/'manifest.json').read_text())
    site=result/'site';vendor=site/'vendor';vendor.mkdir(exist_ok=True)
    for source,dest in names.items():shutil.copyfile(assets/source,vendor/dest)
    template=Path(__file__).parent/'viewer.html'
    html=template.read_text().replace('DISPLAY_MAXZOOM',str(metadata['config']['display_maxzoom']))
    (site/'index.html').write_text(html)
    metadata['optional_viewer']={'maplibre_version':json.loads((assets/'package.json').read_text())['version'],
                                 'template_sha256':sha(template)}
    for p in [site/'index.html',*vendor.iterdir()]:metadata['outputs'][str(p.relative_to(result))]=sha(p)
    (result/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('result',type=Path)
    p.add_argument('--assets',type=Path,required=True,help='MapLibre package directory with dist/, package.json, LICENSE.txt')
    a=p.parse_args();build_viewer(a.result,a.assets)
