"""Pełny test HTTP z rzeczywistym opóźnieniem; trwa około 105 s."""
import json
import sys
import threading
import time
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import HttpClient
from stage4 import crawl, export
from site4 import Handler


def main():
    arrivals = []

    class TimedHandler(Handler):
        def do_GET(self):
            arrivals.append(time.monotonic())
            super().do_GET()

    server = ThreadingHTTPServer(('127.0.0.1', 0), TimedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = HttpClient()
    started = time.monotonic()
    try:
        rows, summary = crawl(f'http://127.0.0.1:{server.server_port}/katalog/1', client, date(2026,10,17))
        gaps = [b-a for a,b in zip(arrivals,arrivals[1:])]
        assert len(rows)==200 and len(arrivals)==205
        assert min(gaps)>=0.5, min(gaps)
        summary['test_http'] = {'czas_s': round(time.monotonic()-started,3),
                                'zadania': len(arrivals), 'minimalny_odstep_s': round(min(gaps),6),
                                'dane_testowe': True}
        output = Path(__file__).resolve().parents[1]/'output'/'etap4'
        export(rows,summary,output)
        print(json.dumps(summary['test_http'],ensure_ascii=False), flush=True)
    finally:
        client.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
