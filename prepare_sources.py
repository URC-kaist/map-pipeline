#!/usr/bin/python3
"""Verify original ZIPs and extract their TIFF/world files without replacing data."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from download_sources import checksum


def prepare(root, manifest):
    for item in json.loads(Path(manifest).read_text())['sources']:
        archive=Path(root)/item['path']
        if checksum(archive)!=item['sha256']:raise ValueError(f'Unverified source ZIP: {archive}')
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if Path(name).name!=name or Path(name).suffix.lower() not in ('.tif','.tfw'):
                    raise ValueError(f'Unexpected archive entry: {name}')
                data=z.read(name);dest=archive.parent/name
                if dest.exists():
                    if hashlib.sha256(data).hexdigest()!=checksum(dest):raise ValueError(f'Existing extraction differs: {dest}')
                else:
                    with tempfile.TemporaryDirectory(dir=archive.parent,prefix='.extract-') as temp:
                        staged=Path(temp)/name;staged.write_bytes(data);staged.rename(dest)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--manifest',type=Path,default=Path(__file__).parent/'sources.json')
    a=p.parse_args();prepare(a.root,a.manifest)
