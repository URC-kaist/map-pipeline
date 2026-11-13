#!/usr/bin/python3
"""Serve the offline viewer and /tiles/ from the same origin."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def create_server(root, bind='127.0.0.1', port=8088):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f'No static root directory: {root}')
    return ThreadingHTTPServer((bind, port), partial(Handler, directory=str(root)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).parent/'output/mdrs-crop/site')
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8088)
    a = p.parse_args()
    with create_server(a.root,a.bind,a.port) as server:
        print(f'Viewer: http://{a.bind}:{server.server_port}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
