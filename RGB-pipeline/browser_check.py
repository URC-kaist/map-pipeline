#!/usr/bin/python3
"""Exercise the viewer with a local headless Chromium-family browser."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from serve import create_server

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
p.add_argument('--browser',type=Path,default=Path('/opt/brave.com/brave/brave'))
a=p.parse_args();root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='rgb-browser-') as temp, create_server(a.output/'site',port=0) as server:
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with open(Path(temp)/'browser.log','w') as log:
        browser=subprocess.Popen([str(a.browser),'--headless','--no-first-run','--no-default-browser-check',
            '--disable-background-networking','--disable-component-update','--disable-dev-shm-usage',
            '--use-angle=swiftshader','--enable-unsafe-swiftshader',
            '--remote-debugging-port=0','--user-data-dir='+temp,'about:blank'],stdout=log,stderr=log)
        try:
            port_file=Path(temp)/'DevToolsActivePort'
            deadline=time.monotonic()+20
            while not port_file.exists():
                if browser.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError((Path(temp)/'browser.log').read_text()[-4000:])
                time.sleep(.1)
            port=port_file.read_text().splitlines()[0]
            subprocess.run(['node',str(root/'browser_check.mjs'),port,
                f'http://127.0.0.1:{server.server_port}',str(root/'evidence/browser.json'),
                str(root/'evidence/viewer.png')],check=True,timeout=100)
        finally:
            browser.terminate()
            try:browser.wait(timeout=10)
            except subprocess.TimeoutExpired:browser.kill();browser.wait()
            server.shutdown();thread.join()
