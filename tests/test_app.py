import importlib
import io
import json
from pathlib import Path
import sys
import threading
import time
import wave
import zipfile

from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('STEM_DATA_DIR', str(tmp_path))
    sys.modules.pop('backend.app', None)
    module = importlib.import_module('backend.app')
    with TestClient(module.app) as client:
        yield module, client, {'Authorization': 'Bearer ' + module.TOKEN}
    module.POOL.shutdown(wait=True)


def wait_job(module, job_id):
    for _ in range(100):
        if job_id not in module.ACTIVE:
            return module.read_job(job_id)
        time.sleep(.02)
    raise AssertionError('worker did not finish')


def test_pairing_and_cors(service):
    module, client, headers = service
    assert client.get('/api/jobs').status_code == 401
    unauthorized = client.get('/api/jobs', headers={'Origin':'https://rinodu.github.io'})
    assert unauthorized.status_code == 401
    assert unauthorized.headers['access-control-allow-origin'] == 'https://rinodu.github.io'
    assert client.get('/api/jobs', headers={**headers, 'Origin': 'https://evil.example'}).status_code == 403
    response = client.options('/api/jobs', headers={'Origin': 'https://rinodu.github.io',
        'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'authorization,content-type',
        'Access-Control-Request-Private-Network': 'true'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'https://rinodu.github.io'
    assert response.headers['access-control-allow-private-network'] == 'true'
    assert client.get('/api/jobs', headers={**headers, 'Host': 'evil.example'}).status_code == 400


def test_validation(service):
    module, client, headers = service
    assert client.post('/api/jobs?filename=x.exe&device=cpu', content=b'a', headers=headers).status_code == 400
    assert client.post('/api/jobs?filename=x.wav&device=cpu', content=b'', headers=headers).status_code == 400
    assert client.post('/api/jobs?filename=x.wav&device=cpu&start=nan', content=b'a', headers=headers).status_code == 422
    assert client.post('/api/jobs?filename=x.wav&device=cpu&seconds=1801', content=b'a', headers=headers).status_code == 422
    assert client.get('/api/jobs/not-a-job/archive', headers=headers).status_code == 404
    assert not list(module.DATA.glob('*/source*'))


def test_jobs_download_retry_and_archive(service, monkeypatch):
    module, client, headers = service
    from backend import pipeline
    def separate(folder, *args):
        path = folder / 'piano.wav'
        path.write_bytes((folder / 'input.wav').read_bytes())
        return {'piano': 'piano.wav'}
    def transcribe(folder, stem, *args):
        (folder / 'piano.mid').write_bytes(b'MThd')
        (folder / 'piano.json').write_text('[{"pitch":60,"start":0,"end":1,"velocity":90}]')
        (folder / 'piano.csv').write_text('start,end,pitch,velocity\n0,1,60,90\n')
        return {'file': 'piano.mid', 'notes': 1, 'engine': 'transkun'}
    monkeypatch.setattr(pipeline, 'separate', separate)
    monkeypatch.setattr(pipeline, 'transcribe', transcribe)
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(44100)
        wav.writeframes(b'\0\0' * 22050)
    response = client.post('/api/jobs?filename=sample.wav&device=cpu&seconds=30', content=stream.getvalue(), headers=headers)
    assert response.status_code == 202, response.text
    job_id = response.json()['id']
    job = wait_job(module, job_id)
    assert job['status'] == 'ready', job
    assert .49 < job['duration'] < .51
    assert client.get(f'/api/jobs/{job_id}/files/piano.wav', headers=headers).content[:4] == b'RIFF'
    assert client.get(f'/api/jobs/{job_id}/files/job.json', headers=headers).status_code == 404
    assert client.get(f'/api/jobs/{job_id}/files/..%2Ftoken.txt', headers=headers).status_code == 404
    ticket = client.post(f'/api/jobs/{job_id}/download?asset=piano.wav', headers=headers)
    assert ticket.status_code == 200
    assert client.get(ticket.json()['url']).content[:4] == b'RIFF'
    assert client.get(ticket.json()['url']).status_code == 404
    assert client.post(f'/api/jobs/{job_id}/download?asset=source.wav', headers=headers).status_code == 404
    assert client.post(f'/api/jobs/{job_id}/download?asset=piano.wav').status_code == 401
    preview = client.post(f'/api/jobs/{job_id}/download?asset=piano.wav&preview=true', headers=headers).json()['url']
    assert client.get(preview, headers={'Range':'bytes=0-31'}).status_code == 206
    assert len(client.get(preview, headers={'Range':'bytes=32-63'}).content) == 32
    assert client.post(f'/api/jobs/{job_id}/download?asset=archive&preview=true', headers=headers).status_code == 400
    assert client.post(f'/api/jobs/{job_id}/midi', json={'stem':'drums'}, headers=headers).status_code == 422
    result = client.post(f'/api/jobs/{job_id}/midi', json={'stem':'piano','engine':'transkun'}, headers=headers)
    assert result.status_code == 202
    assert wait_job(module, job_id)['midi']['piano']['notes'] == 1
    archive = client.get(f'/api/jobs/{job_id}/archive', headers=headers)
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert {'stems/piano.wav', 'piano.mid', 'piano.csv', 'piano.json', 'job.json'} <= set(bundle.namelist())
        assert 'token.txt' not in bundle.namelist()
    def fail(*args):
        raise RuntimeError('sample model failure')
    monkeypatch.setattr(pipeline, 'transcribe', fail)
    client.post(f'/api/jobs/{job_id}/midi', json={'stem':'piano','engine':'transkun'}, headers=headers)
    job = wait_job(module, job_id)
    assert job['status'] == 'error'
    assert job['midi']['piano']['notes'] == 1
    assert client.get(f'/api/jobs/{job_id}/files/piano.wav', headers=headers).status_code == 200


def test_upload_limit_and_queue(service, monkeypatch):
    module, client, headers = service
    monkeypatch.setattr(module, 'MAX_UPLOAD', 4)
    assert client.post('/api/jobs?filename=a.wav&device=cpu', content=b'12345', headers=headers).status_code == 413
    module.ACTIVE.update(['a', 'b', 'c'])
    assert client.post('/api/jobs?filename=a.wav&device=cpu', content=b'1', headers=headers).status_code == 429
    module.ACTIVE.clear()


def test_restart_marks_interrupted(service):
    module, client, headers = service
    job_id = 'a' * 32
    (module.DATA / job_id).mkdir()
    module.save_job({'id':job_id, 'status':'processing', 'stems':{}, 'midi':{}})
    with TestClient(module.app):
        assert module.read_job(job_id)['status'] == 'error'
