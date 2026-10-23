"""One model per process. Transkun reads PCM directly (its CLI forces MP3 decoding)."""
import argparse
import csv
from importlib.resources import files
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--engine", choices=["transkun", "basic-pitch"], required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--onset", type=float, default=0.5)
    parser.add_argument("--minimum-ms", type=float, default=100)
    parser.add_argument("--program", type=int, default=0)
    args = parser.parse_args()
    if args.engine == "transkun":
        import moduleconf
        import soundfile as sf
        import soxr
        import torch
        from transkun.Data import writeMidi
        root = files("transkun") / "pretrained"
        config = moduleconf.parseFromFile(str(root / "2.0.conf"))
        model = config["Model"].module.TransKun(conf=config["Model"].config).to(args.device)
        # Only the checkpoint bundled by the pinned upstream package is loaded.
        checkpoint = torch.load(str(root / "2.0.pt"), map_location=args.device, weights_only=False)
        model.load_state_dict(checkpoint.get("best_state_dict", checkpoint.get("state_dict")), strict=False)
        model.eval()
        audio, sr = sf.read(args.source, dtype="float32", always_2d=True)
        if sr != model.fs:
            audio = soxr.resample(audio, sr, model.fs)
        with torch.inference_mode():
            notes = model.transcribe(torch.from_numpy(audio).to(args.device), discardSecondHalf=False)
        midi = writeMidi(notes)
    else:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
        # Python 3.10 on Windows uses the small bundled ONNX model on CPU.
        _, midi, _ = predict(args.source, model_or_model_path=ICASSP_2022_MODEL_PATH,
                             onset_threshold=args.onset, minimum_note_length=args.minimum_ms)
    rows = []
    for instrument in midi.instruments:
        instrument.program = args.program
        instrument.notes = [n for n in instrument.notes if (n.end - n.start) * 1000 >= args.minimum_ms]
        for note in instrument.notes:
            rows.append({"start": round(float(note.start), 5), "end": round(float(note.end), 5),
                         "pitch": int(note.pitch), "velocity": int(note.velocity)})
    rows.sort(key=lambda n: (n["start"], n["pitch"]))
    midi.write(str(args.output))
    args.output.with_suffix(".json").write_text(json.dumps(rows), encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["start", "end", "pitch", "velocity"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
