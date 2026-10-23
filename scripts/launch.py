import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault('TORCH_HOME', str(Path(sys.prefix).parent / '.local' / 'models'))
DATA = ROOT / '.local'
DATA.mkdir(exist_ok=True)
token_file = DATA / 'token.txt'
if not token_file.exists():
    token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
token = token_file.read_text(encoding='utf-8').strip()
request = urllib.request.Request('http://127.0.0.1:8765/api/health', headers={'Authorization': 'Bearer ' + token})
child = None
try:
    with socket.socket() as probe:
        occupied = probe.connect_ex(('127.0.0.1', 8765)) == 0
    if not occupied:
        child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8765'])
    for attempt in range(90):
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    break
        except Exception:
            if child and child.poll() is not None:
                raise RuntimeError('Backend berhenti. Periksa pesan di atas.')
            if occupied:
                raise RuntimeError('Port 8765 dipakai layanan lain atau token berbeda. Tutup backend lama dahulu.')
            time.sleep(1)
    else:
        raise RuntimeError('Backend belum siap setelah 90 detik.')
    url = 'https://rinodu.github.io/stem-midi-local/#token=' + token
    local = 'http://127.0.0.1:8765/#token=' + token
    print('\nBackend siap. Browser akan membuka GitHub Pages. Jangan tutup jendela ini.')
    print('Jika browser memblokir koneksi, buka versi lokal:\n' + local)
    print('Token pairing (jangan bagikan): ' + token)
    webbrowser.open(url)
    if child:
        child.wait()
except KeyboardInterrupt:
    pass
finally:
    if child and child.poll() is None:
        child.terminate()
        child.wait(timeout=20)
