"""로컬 미리보기 서버: 정적 파일을 캐시 없이 내려준다 (고친 화면이 바로 보이게).

    python3 console/serve.py            # http://127.0.0.1:8777
    python3 console/serve.py 9000
"""
import functools
import http.server
import sys
from pathlib import Path


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    handler = functools.partial(NoCache, directory=str(Path(__file__).parent))
    with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as srv:
        print(f'http://127.0.0.1:{port}')
        srv.serve_forever()
