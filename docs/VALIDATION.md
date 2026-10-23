# Validation — 23 October 2026

## Follow-up: real Bulbel excerpt

User-supplied MP3 tested on seconds 0–5 with six-stem, two-shift CUDA separation. All six WAVs were exactly 5 seconds; piano Transkun MIDI contained 12 parseable notes within the clip. The other stems had RMS approximately -89 to -92 dBFS, over 60 dB below piano, but Basic Pitch initially emitted 13–24 notes from this residual bleed. A conservative absolute-and-relative near-silence gate now exports empty MIDI with a visible warning for such residuals; original WAV stems are retained. Regression tests check that equally quiet whole recordings still reach the model. Current application suite: **6 passed**. This does not establish note-for-note musical accuracy. No user audio is committed to this repository.

## Environment actually tested

- Windows x64, Python 3.10.21, PyTorch/Torchaudio 2.5.1+cu121.
- GPU detected and used: **NVIDIA GeForce GTX 1080, 8 GB**, CUDA available.
- Runtime installed on `E:` because `C:` did not have enough free space. Project source and generated sample results remained in the project directory. No user audio was uploaded to GitHub.
- `pip check`: no broken requirements. `ncls==0.0.68` uses its official Windows CPython wheel, avoiding a C++ toolchain requirement from 0.0.70.

## Automated application checks

`python -m pytest -q`: **5 passed**. Includes authentication, allowed/rejected origins, Private Network Access preflight, invalid filenames/empty uploads/duration limits, upload size/queue limit, actual FFmpeg decoding of a generated WAV, fake model job completion, asset allowlist/path traversal rejection, one-time download tickets, streaming audio Range requests, ZIP contents, preserved outputs after a transcription failure, and interrupted-job handling on restart.

One upstream Starlette/AnyIO deprecation warning is present. Model inference is mocked in these application tests, not in the smoke test below. `node --check frontend/app.js`: passed. PowerShell installer/start scripts parsed successfully. GitHub Actions Windows application checks and Pages deployment succeeded; workflows remain available in the repository Actions tab.

## Real model inference

Command: `python scripts/smoke_models.py --device cuda` using the project runtime.

Fixture: 6-second original synthetic harmonic melody with expected pitches C4/E4/G4/C5 (MIDI 60/64/67/72). This is **not a real piano recording, not a music dataset, and not an accuracy benchmark**.

- `htdemucs_6s` generated all six WAV stems, each with the expected duration.
- Basic Pitch on the clean fixture: 5 notes, pitches 60/64/67/72/**79**. The extra pitch demonstrates a false positive.
- Transkun on the clean synthetic fixture: 2 notes, pitches 64/67. It missed notes; the waveform is not a true piano performance.
- Transkun on the separated piano stem: 4 notes, pitches 60/64/67/72. This one example cannot establish general accuracy.
- Every MIDI was reopened with PrettyMIDI; note pitch/timing and JSON/CSV exports were checked.
- One successful warm-cache run took 34.1 seconds overall on this PC. This is a single integration run, not a promise about processing time or other GPUs.

Machine-readable evidence: [smoke-report.json](smoke-report.json). A failed first run exposed NumPy integer values in JSON output; note exports now normalize numeric values at the serialization boundary, and the full smoke test passed afterward.

## Browser checks

On the deployed `https://rinodu.github.io/stem-midi-local/` frontend, using the Codex in-app browser:

- Rendered UI and offline/pairing failure state checked.
- Successful pairing to `127.0.0.1:8765` with the generated local token; actual GPU name displayed.
- Uploaded the generated fixture through the file chooser; completed real six-stem CUDA separation.
- Created piano MIDI with Transkun (4 notes) and bass MIDI with Basic Pitch (4 notes).
- Opened the piano roll and checked that the four piano notes were visible.
- WAV, MIDI and ZIP downloads completed. ZIP validated with Python `zipfile`; contains all six stems and separate MIDI/CSV/JSON results. A buffered ZIP fetch initially failed in the in-app browser; downloads now use native streaming with short-lived, asset-scoped tickets.
- Final streaming preview loaded the full 6-second piano audio (`readyState=4`, no media error), played to its end, and the final native ZIP download completed again after that change.
- Backend restart preserved completed sample results.
- The Windows start script used the saved external runtime path and started a healthy CUDA backend.

## Not established

RTX 4060 hardware performance, clean-PC installation without uv, other browsers' local-network permission behavior, 30-minute inputs, 4-stem fine-tuned ensemble inference, high-quality 2-shift mode, and accuracy on real music have **not** been tested in this run. CPU fallback is configured but not benchmarked. No SDR or note-level precision/recall claim is made. There is no manual note editor, score export, drum MIDI, or automatic tempo/quantization.
