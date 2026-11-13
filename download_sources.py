#!/usr/bin/python3
"""Download original source ZIPs using curl, verifying recorded SHA-256 hashes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def checksum(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()


def download(entry,root):
    dest=root/entry['path'];dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        if checksum(dest)!=entry['sha256']:raise ValueError(f'Existing file differs: {dest}')
        return {'path':entry['path'],'status':'already verified'}
    with tempfile.TemporaryDirectory(prefix='.download-',dir=dest.parent) as temp:
        candidate=Path(temp)/dest.name
        subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','3',
            '--connect-timeout','20','--max-time','300',entry['url'],'--output',str(candidate)],check=True)
        if checksum(candidate)!=entry['sha256']:raise ValueError(f'Checksum differs for {entry["url"]}')
        if candidate.stat().st_size!=entry['bytes']:raise ValueError('Size mismatch')
        candidate.rename(dest)
    return {'path':entry['path'],'status':'downloaded and verified','bytes':entry['bytes']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--manifest',type=Path,default=Path(__file__).parent/'sources.json')
    p.add_argument('--report',type=Path)
    a=p.parse_args();entries=json.loads(a.manifest.read_text())['sources']
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda e:download(e,a.root),entries))
    text=json.dumps(results,indent=2)+'\n'
    if a.report:a.report.write_text(text)
    print(text)
