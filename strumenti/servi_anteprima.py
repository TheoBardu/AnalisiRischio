#! /usr/bin/env python3
"""
Server locale per l'anteprima dell'interfaccia.

Serve la cartella web/ senza cache, cosi' le modifiche a app.js e app.css si
vedono ricaricando la pagina.

USO: python strumenti/servi_anteprima.py [porta]
"""

import functools
import http.server
import os
import sys

CARTELLA_WEB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')


class SenzaCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()

    def log_message(self, *_):
        pass


def main():
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    gestore = functools.partial(SenzaCache, directory=CARTELLA_WEB)
    with http.server.ThreadingHTTPServer(('127.0.0.1', porta), gestore) as server:
        print(f'anteprima su http://127.0.0.1:{porta}/anteprima.html')
        server.serve_forever()


if __name__ == '__main__':
    sys.exit(main())
