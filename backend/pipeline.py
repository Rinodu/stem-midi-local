"""Model subprocesses release GPU memory between stages; no hosted inference API."""
import json
import os
from pathlib import Path
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
import soundfile as sf

MODELS = {"six": "htdemucs_6s", "four": "htdemucs_ft"}
PITCHED = {"piano": 0, "guitar": 24, "bass": 33, "vocals": 53, "other": 0}


def audio_levels(path):
    energy, count, peak = 0.0, 0, 0.0
    for block in sf.blocks(path, blocksize=44100, dtype="float32", always_2d=True):
        energy += float(np.square(block, dtype=np.float64).sum())
        count += block.size
        peak = max(peak, float(np.max(np.abs(block))))
    return (energy / max(1, count)) ** .5, peak


def run(command, folder, timeout=14400):
    with (folder / "process.log").open("ab") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, env=os.environ.copy())
    if result.returncode:
        raise RuntimeError("Proses model gagal. Buka process.log di folder hasil untuk detail.")


def decode(source, folder, start, seconds):
    target = folder / "input.wav"
    # Decode only a bounded interval, including for compressed files with false metadata.
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-y",
               "-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,flac,mov,ogg,aiff,aac,asf",
               "-ss", str(start), "-i", str(source), "-t", str(seconds or 1801),
               "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(target)]
    run(command, folder, timeout=300)
    info = sf.info(target)
    if info.duration < 0.1 or info.duration > 1800:
        raise ValueError("Audio harus berisi 0,1 detik sampai 30 menit. Gunakan cuplikan untuk file panjang.")
    return target, info.duration


def separate(folder, model, device, quality):
    run([sys.executable, "-m", "demucs", "-n", MODELS[model], "-d", device,
         "--segment", "5", "--shifts", "2" if quality == "high" else "1",
         "--overlap", "0.25", "--float32", "--clip-mode", "clamp", "-j", "0",
         "-o", str(folder / "separated"), str(folder / "input.wav")], folder)
    result = folder / "separated" / MODELS[model] / "input"
    files = sorted(result.glob("*.wav"))
    expected = 6 if model == "six" else 4
    if len(files) != expected:
        raise RuntimeError(f"Model tidak menghasilkan {expected} stem lengkap.")
    return {p.stem: p.relative_to(folder).as_posix() for p in files}


def transcribe(folder, stem, source, engine, device, onset, minimum_ms):
    midi_dir = folder / "midi"
    midi_dir.mkdir(exist_ok=True)
    output = midi_dir / f"{stem}.mid"
    pending = midi_dir / f"{stem}.pending.mid"
    rms, peak = audio_levels(folder / source)
    reference_rms, _ = audio_levels(folder / "input.wav")
    # Only suppress extremely quiet residuals relative to the mix, not quiet recordings.
    if rms == 0 or (peak < .0031623 and rms < .0001 and rms < reference_rms * .003):
        import pretty_midi
        pretty_midi.PrettyMIDI().write(str(pending))
        pending.with_suffix(".json").write_text("[]", encoding="utf-8")
        pending.with_suffix(".csv").write_text("start,end,pitch,velocity\n", encoding="utf-8")
        for suffix in (".mid", ".json", ".csv"):
            pending.with_suffix(suffix).replace(output.with_suffix(suffix))
        return {"file": output.relative_to(folder).as_posix(), "notes": 0,
                "engine": engine, "onset": onset, "minimum_ms": minimum_ms,
                "warning": "Stem nyaris senyap dibanding campuran. MIDI dikosongkan untuk menghindari not dari kebocoran/noise; ini bukan bukti instrumen tidak ada."}
    # Write to temporary files first so a failed retry keeps the previous MIDI.
    run([sys.executable, "-m", "backend.transcribe", str(folder / source), str(pending),
         "--engine", engine, "--device", device, "--onset", str(onset),
         "--minimum-ms", str(minimum_ms), "--program", str(PITCHED[stem])], folder)
    pending.replace(output)
    for suffix in (".json", ".csv"):
        pending.with_suffix(suffix).replace(output.with_suffix(suffix))
    notes = json.loads(output.with_suffix(".json").read_text())
    return {"file": output.relative_to(folder).as_posix(), "notes": len(notes),
            "engine": engine, "onset": onset, "minimum_ms": minimum_ms}
