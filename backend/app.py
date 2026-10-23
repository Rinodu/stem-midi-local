import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal
import uuid
import zipfile

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import pipeline

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("STEM_DATA_DIR", ROOT / ".local")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
TOKEN_FILE = DATA / "token.txt"
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding="utf-8")
TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()
ORIGINS = ["https://rinodu.github.io", "http://127.0.0.1:8765", "http://localhost:8765"]
MAX_UPLOAD = 300 * 1024 * 1024
EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aac", ".wma"}
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)
ACTIVE = set()
UPLOADING = set()


def folder_for(job_id):
    if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
        raise HTTPException(404, "Job tidak ditemukan")
    folder = DATA / job_id
    if not (folder / "job.json").is_file():
        raise HTTPException(404, "Job tidak ditemukan")
    return folder


def read_job(job_id):
    with LOCK:
        return json.loads((folder_for(job_id) / "job.json").read_text(encoding="utf-8"))


def save_job(job):
    with LOCK:
        target = DATA / job["id"] / "job.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)


def update_job(job_id, **changes):
    with LOCK:
        job = read_job(job_id)
        job.update(changes)
        save_job(job)


def execute(job_id, action, options=None):
    folder = folder_for(job_id)
    try:
        job = read_job(job_id)
        if action == "separate":
            update_job(job_id, status="processing", stage="Membaca audio", error=None)
            _, duration = pipeline.decode(folder / job["source"], folder, job["start"], job["seconds"])
            update_job(job_id, duration=duration, stage="Memisahkan instrumen (unduh bobot pada pemakaian pertama)")
            stems = pipeline.separate(folder, job["model"], job["device"], job["quality"])
            update_job(job_id, stems=stems)
        else:
            stem = options.stem
            update_job(job_id, status="processing", stage=f"Membuat MIDI {stem} / {options.engine}", error=None)
            result = pipeline.transcribe(folder, stem, job["stems"][stem], options.engine,
                                         job["device"], options.onset, options.minimum_ms)
            midi = read_job(job_id)["midi"]
            midi[stem] = result
            update_job(job_id, midi=midi)
        update_job(job_id, status="ready", stage="Selesai")
    except Exception as exc:
        update_job(job_id, status="error", stage="Proses berhenti", error=str(exc))
    finally:
        with LOCK:
            ACTIVE.discard(job_id)


@asynccontextmanager
async def lifespan(app):
    for path in DATA.glob("*/job.json"):
        job = json.loads(path.read_text(encoding="utf-8"))
        if job["status"] in {"queued", "processing"}:
            job.update(status="error", stage="Terputus", error="Backend ditutup saat proses. Stem yang sudah selesai tetap tersedia.")
            save_job(job)
    yield


app = FastAPI(title="Stem MIDI Local", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], expose_headers=["Content-Disposition"])


@app.middleware("http")
async def private_api(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and origin not in ORIGINS:
            return JSONResponse({"detail": "Origin tidak diizinkan"}, status_code=403)
        if request.method != "OPTIONS":
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + TOKEN):
                headers = {"Cache-Control": "no-store"}
                if origin in ORIGINS:
                    headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
                return JSONResponse({"detail": "Token pairing salah atau kosong"}, status_code=401, headers=headers)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    if request.method == "OPTIONS" and request.headers.get("origin") in ORIGINS:
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.get("/api/health")
def health():
    import torch
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    return {"ok": True, "gpu": gpu, "cuda": torch.cuda.is_available(), "version": "0.1.0"}


@app.get("/api/jobs")
def jobs():
    with LOCK:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA.glob("*/job.json"),
                key=lambda p: p.stat().st_mtime, reverse=True)]


@app.post("/api/jobs", status_code=202)
async def upload(request: Request, filename: str = Query(min_length=1, max_length=255),
                 model: Literal["six", "four"] = "six", device: Literal["cpu", "cuda"] = "cuda",
                 quality: Literal["balanced", "high"] = "balanced",
                 start: float = Query(0, ge=0, le=7200, allow_inf_nan=False),
                 seconds: int = Query(30, ge=0, le=1800)):
    suffix = Path(filename).suffix.lower()
    if suffix not in EXTENSIONS:
        raise HTTPException(400, "Format audio tidak didukung")
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            raise HTTPException(400, "CUDA tidak tersedia. Pilih CPU atau periksa instalasi driver/PyTorch.")
    job_id = uuid.uuid4().hex
    with LOCK:
        if len(ACTIVE) + len(UPLOADING) >= 3:
            raise HTTPException(429, "Antrean penuh (maksimum 3). Tunggu proses selesai.")
        UPLOADING.add(job_id)
    folder = DATA / job_id
    folder.mkdir()
    source = folder / ("source" + suffix)
    try:
        size = 0
        with source.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Maksimum upload 300 MiB")
                handle.write(chunk)
        if not size:
            raise HTTPException(400, "File kosong")
        job = {"id": job_id, "name": filename.replace("\\", "/").split("/")[-1],
               "source": source.name, "model": model, "device": device, "quality": quality,
               "start": start, "seconds": seconds, "status": "queued", "stage": "Dalam antrean",
               "stems": {}, "midi": {}, "error": None}
        save_job(job)
        with LOCK:
            ACTIVE.add(job_id)
        POOL.submit(execute, job_id, "separate")
        return job
    except BaseException:
        shutil.rmtree(folder)
        raise
    finally:
        with LOCK:
            UPLOADING.discard(job_id)


class MidiOptions(BaseModel):
    stem: Literal["piano", "guitar", "bass", "vocals", "other"]
    engine: Literal["transkun", "basic-pitch"] = "basic-pitch"
    onset: float = Field(0.5, ge=0.1, le=0.9, allow_inf_nan=False)
    minimum_ms: int = Field(100, ge=30, le=1000)


@app.post("/api/jobs/{job_id}/midi", status_code=202)
def midi(job_id: str, options: MidiOptions):
    with LOCK:
        job = read_job(job_id)
        if job_id in ACTIVE or len(ACTIVE) + len(UPLOADING) >= 3:
            raise HTTPException(409, "Job masih berjalan atau antrean penuh")
        if options.stem not in job["stems"]:
            raise HTTPException(400, "Stem belum tersedia")
        if options.engine == "transkun" and options.stem != "piano":
            raise HTTPException(400, "Transkun hanya untuk piano")
        update_job(job_id, status="queued", stage="MIDI dalam antrean", error=None)
        ACTIVE.add(job_id)
        POOL.submit(execute, job_id, "midi", options)
    return read_job(job_id)


@app.get("/api/jobs/{job_id}/files/{asset:path}")
def file(job_id: str, asset: str):
    job = read_job(job_id)
    folder = folder_for(job_id)
    allowed = set(job["stems"].values())
    for item in job["midi"].values():
        path = Path(item["file"])
        allowed.update([path.as_posix(), path.with_suffix(".json").as_posix(), path.with_suffix(".csv").as_posix()])
    if asset not in allowed:
        raise HTTPException(404, "File tidak ditemukan")
    return FileResponse(folder / asset, filename=Path(asset).name)


@app.get("/api/jobs/{job_id}/archive")
def archive(job_id: str):
    with LOCK:
        if job_id in ACTIVE:
            raise HTTPException(409, "Tunggu job selesai sebelum mengunduh ZIP")
        job = read_job(job_id)
        folder = folder_for(job_id)
        target = folder / "results.zip"
        assets = list(job["stems"].values())
        for item in job["midi"].values():
            path = Path(item["file"])
            assets += [path.as_posix(), path.with_suffix(".json").as_posix(), path.with_suffix(".csv").as_posix()]
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as bundle:
            for asset in assets:
                bundle.write(folder / asset, ("stems/" + Path(asset).name) if asset.endswith(".wav") else asset)
            bundle.writestr("job.json", json.dumps(job, indent=2, ensure_ascii=False))
        return FileResponse(target, filename="stem-midi-results.zip")


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
